import React from 'react';

const shell: React.CSSProperties = {
  background: '#f4ead7',
  color: '#161d27',
  borderRadius: 16,
  boxShadow: '0 14px 36px #0008',
  padding: 22,
  fontFamily: 'Arial, sans-serif',
  boxSizing: 'border-box',
};

const kicker: React.CSSProperties = {
  fontSize: 18,
  fontWeight: 800,
  letterSpacing: 1.2,
  textTransform: 'uppercase',
  color: '#ad3334',
  marginBottom: 10,
};

const body: React.CSSProperties = {
  fontSize: 36,
  lineHeight: 1.12,
  fontWeight: 800,
};

export const EvidenceCitationCard: React.FC<{study:string;journal?:string;year?:string|number;n?:string|number;finding:string;citation?:string}> = (p) => (
  <div style={shell}>
    <div style={kicker}>Evidence</div>
    <div style={body}>{p.finding}</div>
    <div style={{marginTop:14,fontSize:20,fontWeight:700}}>
      {p.study}{p.journal ? ` · ${p.journal}` : ''}{p.year ? ` · ${p.year}` : ''}{p.n ? ` · n=${p.n}` : ''}
    </div>
    {p.citation && <div style={{marginTop:8,fontSize:16,color:'#56606d'}}>{p.citation}</div>}
  </div>
);

export const TrialSnapshot: React.FC<{population:string;intervention:string;control:string;endpoint:string;result:string}> = (p) => (
  <div style={shell}>
    <div style={kicker}>Trial snapshot</div>
    <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:14,fontSize:22}}>
      <div><b>Population</b><br/>{p.population}</div>
      <div><b>Intervention</b><br/>{p.intervention}</div>
      <div><b>Control</b><br/>{p.control}</div>
      <div><b>Endpoint</b><br/>{p.endpoint}</div>
    </div>
    <div style={{...body,marginTop:18,fontSize:30}}>{p.result}</div>
  </div>
);

export const EndpointComparison: React.FC<{claimed:string;measured:string}> = ({claimed,measured}) => (
  <div style={{...shell,display:'grid',gridTemplateColumns:'1fr 1fr',gap:18}}>
    <div><div style={kicker}>Claim</div><div style={body}>{claimed}</div></div>
    <div><div style={{...kicker,color:'#2d6a4f'}}>Measured</div><div style={body}>{measured}</div></div>
  </div>
);

export const MechanismDiagram: React.FC<{input:string;mechanism:string;intermediate?:string;outcome:string}> = (p) => {
  const items=[p.input,p.mechanism,p.intermediate,p.outcome].filter(Boolean) as string[];
  return <div style={shell}><div style={kicker}>Proposed mechanism</div>
    <div style={{display:'flex',alignItems:'center',gap:12,flexWrap:'wrap'}}>
      {items.map((x,i)=><React.Fragment key={x}><div style={{padding:'14px 16px',background:'#111622',color:'#fff',borderRadius:10,fontSize:24,fontWeight:800}}>{x}</div>{i<items.length-1&&<div style={{fontSize:34,fontWeight:900}}>→</div>}</React.Fragment>)}
    </div>
  </div>;
};

export const RedFlagCallout: React.FC<{flag:string;why:string}> = ({flag,why}) => (
  <div style={{...shell,borderLeft:'10px solid #ad3334'}}>
    <div style={kicker}>Red flag</div>
    <div style={body}>{flag}</div>
    <div style={{marginTop:12,fontSize:23,fontWeight:700,color:'#4a5360'}}>{why}</div>
  </div>
);

export const ContradictionCard: React.FC<{heard:string;data:string}> = ({heard,data}) => (
  <div style={shell}>
    <div style={kicker}>Correction</div>
    <div style={{fontSize:24,color:'#6b7280',textDecoration:'line-through',marginBottom:14}}>{heard}</div>
    <div style={body}>{data}</div>
  </div>
);

export const BusinessModelCard: React.FC<{buyer:string;payment:string;economics:string;constraint:string}> = (p) => (
  <div style={shell}><div style={kicker}>Business model</div>
    <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:16,fontSize:23}}>
      <div><b>Buyer</b><br/>{p.buyer}</div><div><b>Payment</b><br/>{p.payment}</div>
      <div><b>Economics</b><br/>{p.economics}</div><div><b>Constraint</b><br/>{p.constraint}</div>
    </div>
  </div>
);

export const ThesisCard: React.FC<{idea:string;caveat?:string}> = ({idea,caveat}) => (
  <div style={{...shell,background:'#111622',color:'#fff',borderBottom:'8px solid #ffe19b'}}>
    <div style={{...kicker,color:'#ffe19b'}}>The bigger idea</div>
    <div style={{...body,fontSize:44}}>{idea}</div>
    {caveat && <div style={{marginTop:14,fontSize:21,color:'#c8d0da'}}>{caveat}</div>}
  </div>
);
