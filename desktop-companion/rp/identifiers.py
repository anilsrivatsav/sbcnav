"""Identify explicitly encoded stations/trains; never use a lot's year as its station."""
import re
STATIONS={'SBC','SMVB','YPR','YNK','HSRA','HUP','DPJ','BWT','KJM','BNC','TK','MYS','DMM','BAND','MLO','BNCE','WFD','HDIH','DBU','GBD','DPE','SSPN','HUR','ASK','TTR','GDH','MKL','RNR','SSLT','CPT','RMGM','MAD','MYA','NYH','CMNR','AP','KGI','KPN','JTJ'}
def references(lot):
    code=str(lot.get('lot','')).upper();tokens=re.findall(r'[A-Z0-9]+',code)
    trains=list(dict.fromkeys(re.findall(r'(?<!\d)([1-9]\d{4})(?!\d)',code)))
    stations=[t for t in tokens if t in STATIONS]
    if not stations:
        for token in tokens:
            match=next((s for s in sorted(STATIONS,key=len,reverse=True)if re.match('^'+s+r'(?:CS|MX|TOI|PRK|STGEN|MPS)\d',token)),None)
            if match:stations.append(match)
    if len(stations)>1 and stations[0]=='SBC':stations=stations[1:]
    return {'station':stations[0]if stations else'','train':' / '.join(trains)}
