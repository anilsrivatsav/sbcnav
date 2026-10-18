'use client';

import Link from 'next/link';
import { useState } from 'react';
import { blankEq, parseEqMessage, type EqData } from './parse';
import styles from './eq.module.css';

const fields: { key: keyof EqData; label: string; wide?: boolean }[] = [
  { key: 'applicationDate', label: 'Application date' }, { key: 'diaryNo', label: 'Diary no.' },
  { key: 'train', label: 'Train no. & name' }, { key: 'journeyDate', label: 'Journey date' },
  { key: 'pnr', label: 'PNR' }, { key: 'from', label: 'From' }, { key: 'to', label: 'To' },
  { key: 'travelClass', label: 'Class' }, { key: 'berths', label: 'Berths / seats' },
  { key: 'mobile', label: 'Passenger mobile' }, { key: 'requesterName', label: 'Requested by — name' },
  { key: 'designation', label: 'Designation' }, { key: 'address', label: 'Address', wide: true },
  { key: 'reason', label: 'Special reason of journey', wide: true },
  { key: 'applicantSignature', label: 'Applicant signature text (optional)' },
  { key: 'officer', label: 'Recommending officer (optional)' },
  { key: 'officerMobile', label: 'Officer mobile (optional)' },
];

function EqForm({ data }: { data: EqData }) {
  const row = (number: string, hindi: string, english: string, value: string, className = '') => (
    <tr className={className}>
      <td className={styles.number}>{number}</td><td className={styles.label}>{hindi} / {english}</td><td className={styles.value}>{value}</td>
    </tr>
  );
  return <article className={styles.form}>
    <header className={styles.formHeader}>
      <div className={styles.emblem}>◉</div>
      <div>दक्षिण पश्चिम रेलवे / South Western Railway</div>
      <strong>आपातकालीन कोटा के लिए आवेदन / Application for Emergency Quota</strong>
      <div>तारीख / Date: <span className={styles.date}>{data.applicationDate}</span></div>
    </header>
    <table className={styles.table}><colgroup><col style={{ width: '7%' }}/><col style={{ width: '47%' }}/><col style={{ width: '46%' }}/></colgroup><tbody>
      {row('1.', 'डायरी संख्या', 'DIARY NO.', data.diaryNo)}
      {row('2.', 'गाड़ी संख्या और नाम', 'Train No. & Name', data.train)}
      {row('3.', 'यात्रा की तारीख', 'Date of Journey', data.journeyDate)}
      {row('4.', 'पी एन आर संख्या', 'PNR No.', data.pnr)}
      {row('5.', 'से', 'From', data.from)}
      {row('6.', 'तक', 'To', data.to)}
      {row('7.', 'श्रेणी', 'Class', data.travelClass)}
      {row('8.', 'बर्थ/सीटों की संख्या', 'No. of Berths/Seats', data.berths)}
      <tr className={styles.section}><td>9.</td><td colSpan={2}>यात्रियों का नाम / Name of Passengers</td></tr>
      {data.passengers.map((name, index) => <tr className={styles.passenger} key={index}><td></td><td className={styles.passengerNumber}>{index + 1}).</td><td className={styles.value}>{name}</td></tr>)}
      {row('10.', 'यात्री/यात्रियों का मोबाइल नंबर', 'Mobile No. of passenger(s)', data.mobile, styles.mobileRow)}
      <tr className={styles.section}><td>11.</td><td colSpan={2}>द्वारा अनुरोध किया गया / Requested by</td></tr>
      {row('', 'नाम', 'Name', data.requesterName)}
      {row('', 'पदनाम', 'Design.', data.designation)}
      {row('', 'पता', 'Address', data.address, styles.addressRow)}
      {row('12.', 'यात्रा का विशेष कारण', 'Special Reason of Journey', data.reason, styles.reasonRow)}
      {row('13.', 'आवेदक के हस्ताक्षर', 'Signature of Applicant', data.applicantSignature, styles.signatureRow)}
      <tr className={styles.undertaking}><td colSpan={3}>मैं एतद्द्वारा उस आवेदक की पूरी जिम्मेदारी लेता हूं जिसके लिए मैं बर्थ आवंटन की सिफारिश कर रहा हूं।<br/>I hereby undertake full responsibility of applicant for whom I am recommending for allotment of berth(s).</td></tr>
      <tr className={styles.officerHeading}><td>14.</td><td colSpan={2}>सिफारिश करने वाला अधिकारी / Recommending Officer</td></tr>
      <tr className={styles.officerArea}><td colSpan={2}><span>{data.officerMobile}</span><span className={styles.officerMobile}>मोबाइल नंबर / Mobile No.</span></td><td><span>{data.officer}</span><span className={styles.officerStamp}>हस्ताक्षर एवं मुहर / Signature & Stamp</span></td></tr>
    </tbody></table>
  </article>;
}

export default function EqPage() {
  const [messages, setMessages] = useState(['', '']);
  const [forms, setForms] = useState<EqData[]>([blankEq(), blankEq()]);
  const [status, setStatus] = useState('');
  const [busy, setBusy] = useState(false);
  const update = (index: number, patch: Partial<EqData>) => setForms(old => old.map((form, i) => i === index ? { ...form, ...patch } : form));
  const extract = (index: number) => {
    if (!messages[index].trim()) { setStatus(`Paste a message for form ${index + 1} first.`); return; }
    update(index, parseEqMessage(messages[index]));
    setStatus(`Details extracted for form ${index + 1}. Review all fields before downloading.`);
  };
  const download = async () => {
    const sheet = document.getElementById('eq-pdf-sheet');
    if (!sheet) return;
    setBusy(true); setStatus('Creating the PDF…');
    try {
      await document.fonts.ready;
      const [{ default: html2canvas }, { jsPDF }] = await Promise.all([import('html2canvas-pro'), import('jspdf')]);
      const canvas = await html2canvas(sheet, { scale: 3, backgroundColor: '#ffffff', useCORS: true, logging: false });
      const pdf = new jsPDF({ orientation: 'landscape', unit: 'mm', format: 'a4', compress: true });
      pdf.addImage(canvas.toDataURL('image/jpeg', 0.94), 'JPEG', 0, 0, 297, 210);
      pdf.save(`EQ-applications-${new Date().toISOString().slice(0, 10)}.pdf`);
      setStatus('PDF downloaded. Print it on A4 paper in landscape orientation at actual size.');
    } catch (error) { setStatus(error instanceof Error ? `PDF generation failed: ${error.message}` : 'PDF generation failed.'); }
    finally { setBusy(false); }
  };
  return <main className={styles.page}>
    <div className={styles.top}><div><Link href="/" className={styles.back}>← Dashboard</Link><h1>Emergency Quota forms</h1><p>Paste up to two requests, review the extracted details, then download one landscape A4 PDF with two upright forms.</p></div><button className={styles.download} disabled={busy} onClick={download}>{busy ? 'Preparing PDF…' : 'Download 2-form PDF'}</button></div>
    <p className={styles.note}>Messages stay in this browser. The form leaves signature and officer details blank unless you enter them.</p>
    <div className={styles.editors}>{forms.map((form, index) => <section className={styles.editor} key={index}><h2>Form {index + 1}</h2><label className={styles.messageLabel} htmlFor={`eq-message-${index}`}>Request message</label><textarea id={`eq-message-${index}`} value={messages[index]} onChange={event => setMessages(old => old.map((item, i) => i === index ? event.target.value : item))} placeholder="Example: Train 16348, DOJ 16/10/2026, PNR 4656529053, from CCT to KQJ, class SL, 2 berths. Passenger 1: Anitha (F/37). Passenger 2: Akash (M/16). Mobile: 8086755383. Requested by: Krishna Raj. Designation: CCTC. Reason: Travelling home with child."/><button className={styles.extract} onClick={() => extract(index)}>Extract details</button><div className={styles.fields}>{fields.map(field => <label key={field.key} className={field.wide ? styles.wide : ''}><span>{field.label}</span>{field.wide ? <textarea value={form[field.key] as string} onChange={event => update(index, { [field.key]: event.target.value })} rows={2}/> : <input value={form[field.key] as string} onChange={event => update(index, { [field.key]: event.target.value })}/>}</label>)}{form.passengers.map((passenger, passengerIndex) => <label key={passengerIndex}><span>Passenger {passengerIndex + 1}</span><input value={passenger} onChange={event => update(index, { passengers: form.passengers.map((name, i) => i === passengerIndex ? event.target.value : name) })}/></label>)}</div></section>)}</div>
    <div className={styles.previewHeading}><h2>A4 landscape preview</h2><span>{status || 'Two A5-sized forms on one sheet'}</span></div>
    <div className={styles.previewScroller}><div id="eq-pdf-sheet" className={styles.sheet}><EqForm data={forms[0]}/><div className={styles.cutLine}/><EqForm data={forms[1]}/></div></div>
  </main>;
}
