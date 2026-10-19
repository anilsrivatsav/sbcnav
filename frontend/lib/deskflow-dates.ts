// API auction dates are ISO dates; keep missing dates after dated records.
export function latestAuctionFirst(a:{date?:string},b:{date?:string}){
  return (b.date||"").slice(0,10).localeCompare((a.date||"").slice(0,10));
}
