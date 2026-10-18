'use client';

import { useEffect, useMemo, useState, type ChangeEvent, type FormEvent } from 'react';
import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';
import { Booking, Holiday, Proposal, categories, sourceBookings, findDate, labelDate, labelTime, normalizeDate, normalizeTime, readCSV, csv, nextIdentifiers } from '../../lib/eauction-scheduler';
import './eauction.css';

type Stored = { holidays: Holiday[]; bookings: Booking[]; showSource: boolean };
const initial: Stored = { holidays: [], bookings: [], showSource: true };
const storageKey = 'eauction-planner-next-v1';
function todayISO() { const now = new Date(); return new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0,10); }
function download(name: string, content: string) { const url = URL.createObjectURL(new Blob([content], {type:'text/csv;charset=utf-8'})); const link=document.createElement('a'); link.href=url; link.download=name; link.click(); setTimeout(()=>URL.revokeObjectURL(url),3000); }

export default function AuctionSchedulePage() {
  const [data,setData]=useState<Stored>(initial);
  const [loaded,setLoaded]=useState(false);
  const [category,setCategory]=useState('');
  const [currentDate,setCurrentDate]=useState('');
  const [proposal,setProposal]=useState<Proposal|null>(null);
  const [holidayDate,setHolidayDate]=useState('');
  const [holidayName,setHolidayName]=useState('');
  const [message,setMessage]=useState('');
  const [syncKey,setSyncKey]=useState('');
  const [syncing,setSyncing]=useState<string|null>(null);
  const time=categories.find(item=>item.name===category)?.time||'';
  const bookings=useMemo(()=>[...(data.showSource?sourceBookings:[]),...data.bookings],[data]);
  const identifiers=useMemo(()=>category&&currentDate?nextIdentifiers(category,bookings,Number(currentDate.slice(0,4))):null,[category,bookings,currentDate]);
  const sortedBookings=[...bookings].sort((a,b)=>a.date.localeCompare(b.date)||a.time.localeCompare(b.time));
  const sortedHolidays=[...data.holidays].sort((a,b)=>a.date.localeCompare(b.date));

  useEffect(()=>{try{const saved=JSON.parse(localStorage.getItem(storageKey)||'null') as Partial<Stored>|null;if(saved)setData({...initial,...saved});}catch{}setCurrentDate(todayISO());setLoaded(true);const timer=window.setInterval(()=>setCurrentDate(todayISO()),60000);return()=>window.clearInterval(timer);},[]);
  useEffect(()=>{if(loaded)localStorage.setItem(storageKey,JSON.stringify(data));},[data,loaded]);
  useEffect(()=>{if(!currentDate||!category){setProposal(null);return;}try{setProposal(findDate({noticeDate:currentDate,category,time,subject:'',holidays:data.holidays,bookings}));setMessage('');}catch(error){setProposal(null);setMessage(error instanceof Error?error.message:'Could not calculate a date.');}},[currentDate,category,time,data.holidays,bookings]);

  function save() {
    if(!proposal)return;
    const today=todayISO();
    const current=findDate({noticeDate:today,category:proposal.category,time:proposal.time,subject:'',holidays:data.holidays,bookings});
    if(current.date!==proposal.date||today!==proposal.noticeDate){setCurrentDate(today);setProposal(current);setMessage('Date updated. Review it before saving.');return;}
    const {scheduleId,catalogueId}=nextIdentifiers(proposal.category,bookings,Number(today.slice(0,4)));
    const booking:Booking={id:crypto.randomUUID(),date:proposal.date,time:proposal.time,category:proposal.category,subject:'',status:'scheduled',noticeDate:today,scheduleId,catalogueId};
    setData(value=>({...value,bookings:[...value.bookings,booking]}));
    setMessage('Schedule row saved.');
  }
  function changeStatus(booking:Booking,status:Booking['status']){setData(value=>({...value,bookings:value.bookings.map(item=>item.id===booking.id?{...item,status,syncedAt:undefined}:item)}));setMessage(`${status==='scheduled'?'Scheduled':status==='cancelled'?'Cancelled':'Withdrawn'} locally.${booking.sourceFile?' Imported rows cannot be sent from this app.':' Use Send to Google Sheet to update the workbook.'}`);}
  async function syncBooking(booking:Booking){
    if(!syncKey.trim()){setMessage('Enter the Sheet sync key below before sending.');return;}
    setSyncing(booking.id);setMessage('Sending row to Google Sheet…');
    try{
      const response=await fetch('/api/eauction/sheets',{method:'POST',headers:{'Content-Type':'application/json','x-sync-key':syncKey},body:JSON.stringify({booking})});
      const result=await response.json();
      if(!response.ok)throw new Error(result.error||'Could not send the row.');
      setData(value=>({...value,bookings:value.bookings.map(item=>item.id===booking.id?{...item,scheduleId:result.scheduleId,catalogueId:result.catalogueId,sheetRow:result.row,sheetTab:result.tab,syncedAt:result.syncedAt}:item)}));
      setMessage(`Sent to ${result.tab}, row ${result.row}.`);
    }catch(error){setMessage(error instanceof Error?error.message:'Could not send the row.');}
    finally{setSyncing(null);}
  }
  function addHoliday(event:FormEvent){event.preventDefault();if(!holidayDate||!holidayName.trim())return;setData(value=>({...value,holidays:[...value.holidays.filter(item=>item.date!==holidayDate),{date:holidayDate,name:holidayName.trim()}]}));setHolidayDate('');setHolidayName('');}
  async function importHolidays(event:ChangeEvent<HTMLInputElement>){const file=event.target.files?.[0];if(!file)return;const imported:Holiday[]=readCSV(await file.text()).flatMap(row=>{const date=normalizeDate(row[0]||''),name=row[1]?.trim();return date&&name?[{date,name}]:[];});setData(value=>{const map=new Map(value.holidays.map(item=>[item.date,item]));imported.forEach(item=>map.set(item.date,item));return {...value,holidays:[...map.values()]};});setMessage(imported.length+' holidays imported.');event.target.value='';}
  async function importBookings(event:ChangeEvent<HTMLInputElement>){const file=event.target.files?.[0];if(!file)return;const imported:Booking[]=[];for(const row of readCSV(await file.text())){const date=normalizeDate(row[0]||''),bookedTime=normalizeTime(row[1]||'');const itemCategory=row[2]?.trim();if(!date||!bookedTime||!itemCategory)continue;imported.push({id:crypto.randomUUID(),date,time:bookedTime,category:itemCategory,scheduleId:row[3]?.trim()||'',catalogueId:row[4]?.trim()||'',subject:'',status:/withdrawn/i.test(row[5]||'')?'withdrawn':/cancelled/i.test(row[5]||'')?'cancelled':'scheduled',sourceFile:file.name});}setData(value=>{const existing=new Set(value.bookings.map(item=>[item.date,item.time,item.category,item.scheduleId,item.catalogueId].join('|')));const fresh=imported.filter(item=>{const key=[item.date,item.time,item.category,item.scheduleId,item.catalogueId].join('|');if(existing.has(key))return false;existing.add(key);return true;});return {...value,bookings:[...value.bookings,...fresh],showSource:fresh.length?false:value.showSource};});setMessage(imported.length+' rows read from CSV.');event.target.value='';}
  function exportBookings(){download('eauction-schedule.csv',csv([['Date','Time','Category','EA Schedule ID','Catalogue ID','Status'],...bookings.map(item=>[item.date,item.time,item.category,item.scheduleId||'',item.catalogueId||'',item.status])]));}
  function exportHolidays(){download('eauction-holidays.csv',csv([['Date','Holiday'],...sortedHolidays.map(item=>[item.date,item.name])]));}

  return <main className="eauction-sheet sheet">
    <header className="sheet-header"><div className="title"><Link href="/" className="back-link" aria-label="Back to SBCNAV" title="Back to SBCNAV"><ArrowLeft size={18}/></Link><span className="file-icon">▦</span><div><h1>Auction Schedule</h1><p>Automated eAuction date planner</p></div></div><button className="button outline" onClick={exportBookings}>Download schedule CSV</button></header>
    <section className="work-area">
      <div className="section-title"><h2>New row</h2><span>Choose a category. Date and time fill automatically.</span></div>
      <div className="entry-form">
        <label className="category-field">1. Category<select value={category} onChange={event=>setCategory(event.target.value)}><option value="">Select category</option>{categories.map(item=><option key={item.name}>{item.name}</option>)}</select></label>
        <div className="auto-field"><span>2. Today</span><strong>{currentDate?labelDate(currentDate):'—'}</strong></div>
        <div className="auto-field"><span>Auction date</span><strong>{proposal?labelDate(proposal.date):'—'}</strong></div>
        <div className="auto-field"><span>Time</span><strong>{time?labelTime(time):'—'}</strong></div>
      </div>
      {proposal&&<div className="result-line"><span className="valid">✓ Available</span><span>{proposal.daysAfterNotice} days from today{proposal.skipped.length?' · '+proposal.skipped.length+' unavailable date(s) skipped':''}</span><span>Saturday, Sunday and listed holidays excluded</span></div>}
      <div className="id-row"><label>EA Schedule ID <small>Next number for this category</small><input value={identifiers?.scheduleId||''} placeholder="Select category" readOnly /></label><label>Catalogue ID <small>Next number across all auctions</small><input value={identifiers?.catalogueId||''} placeholder="Select category" readOnly /></label><button className="button primary" disabled={!proposal} onClick={save}>Add to schedule</button></div>
      {message&&<p className="message" role="status">{message}</p>}
      <div className="table-heading"><h2>Schedule</h2><div><label className="button outline file-button">Import CSV<input type="file" accept=".csv,text/csv" onChange={importBookings} hidden /></label><button className="button text" onClick={()=>setData(value=>({...value,showSource:!value.showSource}))}>{data.showSource?'Hide':'Show'} sheet snapshot</button></div></div>
      <div className="table-scroll"><table className="grid"><thead><tr><th className="row-number">#</th><th>Date</th><th>Time</th><th>Category</th><th>EA Schedule ID</th><th>Catalogue ID</th><th>Status</th><th>Actions</th></tr></thead><tbody>{sortedBookings.map((item,index)=><tr key={item.id} className={item.status==='scheduled'?'scheduled':'inactive'}><td className="row-number">{index+1}</td><td>{item.date}</td><td>{labelTime(item.time)}</td><td>{item.category}</td><td>{item.scheduleId||'—'}</td><td>{item.catalogueId||'—'}</td><td><strong>{item.status==='scheduled'?'Scheduled':item.status==='cancelled'?'Cancelled':'Withdrawn'}</strong>{!item.source&&!item.sourceFile&&<small className="sync-state">{item.syncedAt?' · In Google Sheet':' · Not sent'}</small>}</td><td className="actions-cell">{!item.source&&!item.sourceFile&&<button className="row-action send-action" disabled={syncing===item.id} onClick={()=>syncBooking(item)}>{syncing===item.id?'Sending…':'Send to Google Sheet'}</button>}{!item.source&&(item.status==='scheduled'?<><button className="row-action danger" onClick={()=>changeStatus(item,'cancelled')}>Cancel</button><button className="row-action danger" onClick={()=>changeStatus(item,'withdrawn')}>Withdraw</button></>:<button className="row-action" onClick={()=>changeStatus(item,'scheduled')}>Restore</button>)}</td></tr>)}{!sortedBookings.length&&<tr><td colSpan={8} className="empty">No schedule rows yet.</td></tr>}</tbody></table></div>
      <div className="sheet-sync"><label>Google Sheet sync key <input type="password" autoComplete="off" value={syncKey} onChange={event=>setSyncKey(event.target.value)} placeholder="Enter key to send rows" /></label><span>Only rows created in this app can be sent. A changed status is sent when you press the row’s button again.</span></div>
      <p className="hint">ID numbers start from the linked sheet snapshot and include saved or imported rows. On send, the server checks the live workbook and assigns the latest available IDs. CSV columns: Date, Time, Category, EA Schedule ID, Catalogue ID, Status.</p>
      <details className="holidays"><summary>Holidays <span>{sortedHolidays.length} dates</span></summary><div className="holiday-content"><p>Add the official holidays applicable to your auctions. These dates are excluded automatically.</p><form onSubmit={addHoliday} className="holiday-form"><input type="date" value={holidayDate} onChange={event=>setHolidayDate(event.target.value)} required /><input value={holidayName} onChange={event=>setHolidayName(event.target.value)} placeholder="Holiday name" required /><button className="button outline" type="submit">Add</button></form><div className="holiday-actions"><label className="button outline file-button">Import holidays CSV<input type="file" accept=".csv,text/csv" onChange={importHolidays} hidden /></label><button className="button text" onClick={exportHolidays}>Download holidays CSV</button></div>{sortedHolidays.map(item=><div className="holiday-row" key={item.date}><span>{item.date}</span><span>{item.name}</span><button className="row-action" onClick={()=>setData(value=>({...value,holidays:value.holidays.filter(holiday=>holiday.date!==item.date)}))}>Remove</button></div>)}{!sortedHolidays.length&&<p className="hint">No holidays entered. Add your official list before finalizing dates.</p>}</div></details>
    </section><footer>Saved in this browser · Source: Auction Schedule workbook · First available date at least 15 calendar days from today</footer>
  </main>;
}
