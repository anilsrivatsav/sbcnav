'use client';

import { useEffect, useMemo, useRef, useState, type ChangeEvent, type FormEvent } from 'react';
import Link from 'next/link';
import { ArrowLeft, Ban, CircleX, CloudUpload, RotateCcw } from 'lucide-react';
import { Booking, Holiday, Proposal, auctionDateError, identifierError, categories, sourceBookings, findDate, labelDate, labelTime, normalizeDate, normalizeTime, readCSV, csv, nextIdentifiers } from '../../lib/eauction-scheduler';
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
  const [editAutomatic,setEditAutomatic]=useState(false);
  const [editedDate,setEditedDate]=useState<string|null>(null);
  const [editedScheduleId,setEditedScheduleId]=useState<string|null>(null);
  const [editedCatalogueId,setEditedCatalogueId]=useState<string|null>(null);
  const [currentDate,setCurrentDate]=useState('');
  const [proposal,setProposal]=useState<Proposal|null>(null);
  const [holidayDate,setHolidayDate]=useState('');
  const [holidayName,setHolidayName]=useState('');
  const [message,setMessage]=useState('');
  const [liveRows,setLiveRows]=useState<Booking[]|null>(null);
  const [syncing,setSyncing]=useState<string[]>([]);
  const syncRequests=useRef(new Map<string,{status:Booking['status'];promise:Promise<void>}>());
  const time=categories.find(item=>item.name===category)?.time||'';
  const bookings=useMemo(()=>{
    const own=new Set(data.bookings.map(item=>`${item.catalogueId}|${item.date}|${item.time}|${item.category}`));
    return [...(data.showSource?(liveRows??sourceBookings).filter(item=>!own.has(`${item.catalogueId}|${item.date}|${item.time}|${item.category}`)):[]),...data.bookings];
  },[data,liveRows]);
  const auctionDate=editedDate??proposal?.date??'';
  const identifiers=useMemo(()=>category&&currentDate?nextIdentifiers(category,bookings,Number((auctionDate||currentDate).slice(0,4))):null,[category,bookings,currentDate,auctionDate]);
  const scheduleId=editedScheduleId??identifiers?.scheduleId??'';
  const catalogueId=editedCatalogueId??identifiers?.catalogueId??'';
  const dateError=proposal?auctionDateError(auctionDate,currentDate,time,data.holidays,bookings):null;
  const idError=proposal?identifierError(scheduleId,catalogueId,category,bookings):null;
  const sortedBookings=[...bookings].sort((a,b)=>a.date.localeCompare(b.date)||a.time.localeCompare(b.time));
  const sortedHolidays=[...data.holidays].sort((a,b)=>a.date.localeCompare(b.date));

  useEffect(()=>{try{const saved=JSON.parse(localStorage.getItem(storageKey)||'null') as Partial<Stored>|null;if(saved)setData({...initial,...saved});}catch{}setCurrentDate(todayISO());setLoaded(true);const timer=window.setInterval(()=>setCurrentDate(todayISO()),60000);return()=>window.clearInterval(timer);},[]);
  useEffect(()=>{let active=true;fetch('/api/mcdo/eauction',{cache:'no-store'}).then(async response=>{if(!response.ok)return null;const result=await response.json();return Array.isArray(result.data)?result.data as Booking[]:null;}).then(rows=>{if(active&&rows)setLiveRows(rows);}).catch(()=>{});return()=>{active=false;};},[]);
  useEffect(()=>{if(loaded)localStorage.setItem(storageKey,JSON.stringify(data));},[data,loaded]);
  useEffect(()=>{if(!currentDate||!category){setProposal(null);return;}try{setProposal(findDate({noticeDate:currentDate,category,time,subject:'',holidays:data.holidays,bookings}));setMessage('');}catch(error){setProposal(null);setMessage(error instanceof Error?error.message:'Could not calculate a date.');}},[currentDate,category,time,data.holidays,bookings]);

  function save() {
    if(!proposal)return;
    const today=todayISO();
    const current=findDate({noticeDate:today,category:proposal.category,time:proposal.time,subject:'',holidays:data.holidays,bookings});
    if(today!==proposal.noticeDate||(!editAutomatic&&current.date!==proposal.date)){setCurrentDate(today);setProposal(current);setMessage('Date updated. Review it before saving.');return;}
    const error=auctionDateError(auctionDate,today,time,data.holidays,bookings)||identifierError(scheduleId,catalogueId,category,bookings);
    if(error){setMessage(error);return;}
    const automatic=nextIdentifiers(category,bookings,Number(auctionDate.slice(0,4)));
    const booking:Booking={id:crypto.randomUUID(),date:auctionDate,time:proposal.time,category:proposal.category,subject:'',status:'scheduled',noticeDate:today,scheduleId,catalogueId,manualScheduleId:editAutomatic&&scheduleId!==automatic.scheduleId,manualCatalogueId:editAutomatic&&catalogueId!==automatic.catalogueId};
    setData(value=>({...value,bookings:[...value.bookings,booking]}));
    setEditedDate(null);setEditedScheduleId(null);setEditedCatalogueId(null);
    setMessage('Schedule row saved. Sending to Google Sheet…');
    void syncBooking(booking);
  }
  function changeStatus(booking:Booking,status:Booking['status']){
    const changed={...booking,status,syncedAt:undefined};
    setData(value=>({...value,bookings:value.bookings.some(item=>item.id===booking.id)?value.bookings.map(item=>item.id===booking.id?changed:item):[...value.bookings,changed]}));
    if(booking.sourceFile){setMessage('Imported CSV row updated in this browser.');return;}
    void syncBooking(changed);
  }
  function syncBooking(booking:Booking):Promise<void>{
    const active=syncRequests.current.get(booking.id);
    if(active)return active.status===booking.status?active.promise:active.promise.then(()=>syncBooking(booking));
    const promise=sendBooking(booking).finally(()=>{if(syncRequests.current.get(booking.id)?.promise===promise)syncRequests.current.delete(booking.id);});
    syncRequests.current.set(booking.id,{status:booking.status,promise});
    return promise;
  }
  async function sendBooking(booking:Booking){
    setSyncing(value=>[...new Set([...value,booking.id])]);setMessage('Sending row to Google Sheet…');
    try{
      const response=await fetch('/api/mcdo/eauction',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({booking,holidays:data.holidays})});
      const result=await response.json();
      if(!response.ok)throw new Error(response.status===401?'Sign in to the SBCNAV updater to enable automatic Sheet sync.':result.detail||result.error||'Could not send the row.');
      const saved=result.data;
      setData(value=>({...value,bookings:value.bookings.map(item=>item.id===booking.id?{...item,scheduleId:saved.scheduleId,catalogueId:saved.catalogueId,sheetRow:saved.row,sheetTab:saved.tab,syncedAt:item.status===booking.status?saved.syncedAt:undefined}:item)}));
      setMessage(`Saved in Google Sheet: ${saved.tab}, row ${saved.row}.`);
    }catch(error){setMessage(error instanceof Error?error.message:'Could not send the row.');}
    finally{setSyncing(value=>value.filter(id=>id!==booking.id));}
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
        <label className="category-field">1. Category<select value={category} onChange={event=>{setCategory(event.target.value);setEditedDate(null);setEditedScheduleId(null);setEditedCatalogueId(null);}}><option value="">Select category</option>{categories.map(item=><option key={item.name}>{item.name}</option>)}</select></label>
        <div className="auto-field"><span>2. Today</span><strong>{currentDate?labelDate(currentDate):'—'}</strong></div>
        <div className="auto-field"><span>Auction date</span>{editAutomatic?<input type="date" aria-label="Auction date" value={auctionDate} onChange={event=>setEditedDate(event.target.value)} disabled={!proposal}/>:<strong>{proposal?labelDate(auctionDate):'—'}</strong>}</div>
        <div className="auto-field"><span>Time</span><strong>{time?labelTime(time):'—'}</strong></div>
      </div>
      <label className="edit-toggle"><input type="checkbox" checked={editAutomatic} onChange={event=>{setEditAutomatic(event.target.checked);setEditedDate(null);setEditedScheduleId(null);setEditedCatalogueId(null);setMessage('');}}/> Edit auction date and IDs</label>
      {proposal&&<div className="result-line"><span className={dateError||idError?'invalid':'valid'}>{dateError||idError||'✓ Available'}</span>{!editAutomatic&&<span>{proposal.daysAfterNotice} days from today{proposal.skipped.length?' · '+proposal.skipped.length+' unavailable date(s) skipped':''}</span>}<span>Saturday, Sunday and listed holidays excluded</span></div>}
      <div className="id-row"><label>EA Schedule ID <small>Next number for this category</small><input value={scheduleId} placeholder="Select category" readOnly={!editAutomatic} onChange={event=>setEditedScheduleId(event.target.value)} /></label><label>Catalogue ID <small>Next number across all auctions</small><input value={catalogueId} placeholder="Select category" readOnly={!editAutomatic} onChange={event=>setEditedCatalogueId(event.target.value)} /></label><button className="button primary" disabled={!proposal||!!dateError||!!idError} onClick={save}>Add to schedule</button></div>
      {message&&<p className="message" role="status">{message}</p>}
      <div className="table-heading"><div className="table-title"><h2>Schedule</h2><span className="row-count">{sortedBookings.length} auctions</span></div><div><label className="button outline file-button">Import CSV<input type="file" accept=".csv,text/csv" onChange={importBookings} hidden /></label><button className="button text" onClick={()=>setData(value=>({...value,showSource:!value.showSource}))}>{data.showSource?'Hide':'Show'} sheet snapshot</button></div></div>
      <div className="table-scroll"><table className="grid">
        <colgroup><col className="number-col"/><col className="date-col"/><col className="time-col"/><col className="category-col"/><col className="schedule-col"/><col className="catalogue-col"/><col className="actions-col"/></colgroup>
        <thead><tr><th className="row-number">#</th><th>Date</th><th>Time</th><th>Category</th><th>EA Schedule ID</th><th>Catalogue ID</th><th>Actions</th></tr></thead>
        <tbody>{sortedBookings.map((item,index)=><tr key={item.id} className={item.status==='scheduled'?'scheduled':'inactive'}>
          <td className="row-number">{String(index+1).padStart(2,'0')}</td>
          <td className="date-cell">{labelDate(item.date)}</td>
          <td className="time-cell">{labelTime(item.time)}</td>
          <td><span className="category-chip">{item.category}</span></td>
          <td className="id-cell"><span title={item.scheduleId||''}>{item.scheduleId||'—'}</span></td>
          <td className="id-cell"><span title={item.catalogueId||''}>{item.catalogueId||'—'}</span></td>
          <td><div className="actions-cell">
            {item.status==='scheduled'?<>
              <button className="icon-action danger" title="Cancel auction" aria-label={`Cancel ${item.catalogueId||'auction'}`} disabled={syncing.includes(item.id)} onClick={()=>changeStatus(item,'cancelled')}><CircleX size={17}/></button>
              <button className="icon-action danger" title="Withdraw auction" aria-label={`Withdraw ${item.catalogueId||'auction'}`} disabled={syncing.includes(item.id)} onClick={()=>changeStatus(item,'withdrawn')}><Ban size={17}/></button>
            </>:<button className="icon-action restore" title="Restore auction" aria-label={`Restore ${item.catalogueId||'auction'}`} disabled={syncing.includes(item.id)} onClick={()=>changeStatus(item,'scheduled')}><RotateCcw size={17}/></button>}
            {!item.source&&!item.sourceFile&&!item.syncedAt&&<button className="icon-action sync-action" title="Retry Google Sheet sync" aria-label={`Sync ${item.catalogueId||'auction'} to Google Sheet`} disabled={syncing.includes(item.id)} onClick={()=>syncBooking(item)}><CloudUpload size={17}/></button>}
            <span className={`status-light ${item.status}`} role="img" aria-label={`${item.status==='scheduled'?'Scheduled':item.status==='cancelled'?'Cancelled':'Withdrawn'}${!item.sourceFile?item.syncedAt||liveRows&&item.source?' in Google Sheet':' pending sync':''}`} title={`${item.status==='scheduled'?'Scheduled':item.status==='cancelled'?'Cancelled':'Withdrawn'} · ${item.sourceFile?'Imported CSV':item.syncedAt||liveRows&&item.source?'In Google Sheet':item.source?'Sheet snapshot':'Pending sync'}`}/>
          </div></td>
        </tr>)}{!sortedBookings.length&&<tr><td colSpan={7} className="empty">No schedule rows yet.</td></tr>}</tbody>
      </table></div>
      <p className="hint">ID numbers include the live workbook when connected. New rows sync automatically; use the cloud icon to retry an unsynced new row. IDs edited with the checkbox are kept if available. CSV columns: Date, Time, Category, EA Schedule ID, Catalogue ID, Status.</p>
      <details className="holidays"><summary>Holidays <span>{sortedHolidays.length} dates</span></summary><div className="holiday-content"><p>Add the official holidays applicable to your auctions. These dates are excluded automatically.</p><form onSubmit={addHoliday} className="holiday-form"><input type="date" value={holidayDate} onChange={event=>setHolidayDate(event.target.value)} required /><input value={holidayName} onChange={event=>setHolidayName(event.target.value)} placeholder="Holiday name" required /><button className="button outline" type="submit">Add</button></form><div className="holiday-actions"><label className="button outline file-button">Import holidays CSV<input type="file" accept=".csv,text/csv" onChange={importHolidays} hidden /></label><button className="button text" onClick={exportHolidays}>Download holidays CSV</button></div>{sortedHolidays.map(item=><div className="holiday-row" key={item.date}><span>{item.date}</span><span>{item.name}</span><button className="row-action" onClick={()=>setData(value=>({...value,holidays:value.holidays.filter(holiday=>holiday.date!==item.date)}))}>Remove</button></div>)}{!sortedHolidays.length&&<p className="hint">No holidays entered. Add your official list before finalizing dates.</p>}</div></details>
    </section><footer>Saved in this browser · Source: Auction Schedule workbook · First available date at least 15 calendar days from today</footer>
  </main>;
}
