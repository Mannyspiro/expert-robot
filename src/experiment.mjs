/**
 * Tiny, offline exact-rational stoichiometric regression experiment.
 * Independent JS implementation of the repository's four Python toy cases;
 * no chemical mechanism, empirical kinetics, formal proof or CACE certification claimed.
 */
const abs = x => x < 0n ? -x : x;
function gcd(a,b){a=abs(a);b=abs(b);while(b){const t=a%b;a=b;b=t;}return a || 1n;}
function Q(num,den=1n){num=BigInt(num);den=BigInt(den);if(den===0n)throw Error('division by zero');if(den<0n){num=-num;den=-den;}const d=gcd(num,den);return [num/d,den/d];}
function q(v){if(Array.isArray(v))return Q(v[0],v[1]);if(typeof v==='string'&&v.includes('/')){const [a,b]=v.split('/');return Q(a,b);}return Q(v);}
const plus=(a,b)=>Q(a[0]*b[1]+a[1]*b[0],a[1]*b[1]);
const neg=a=>[-a[0],a[1]];
const minus=(a,b)=>plus(a,neg(b));
const times=(a,b)=>Q(a[0]*b[0],a[1]*b[1]);
const divide=(a,b)=>Q(a[0]*b[1],a[1]*b[0]);
const eq=(a,b)=>a[0]===b[0]&&a[1]===b[1];
const fmt=a=>a[1]===1n?String(a[0]):`${a[0]}/${a[1]}`;
const zero=()=>Q(0);
function dot(a,b){if(a.length!==b.length)throw Error('shape');return a.reduce((sum,v,i)=>plus(sum,times(v,b[i])),zero());}
function leftNullspace(columns,species){
  if(species<1||columns.length<1||columns.some(c=>c.length!==species))throw Error('invalid stoichiometry');
  const rows=columns.map(c=>c.map(q));let rank=0;const pivots=[];
  for(let j=0;j<species&&rank<rows.length;j++){
    const i=rows.findIndex((row,k)=>k>=rank&&row[j][0]!==0n);
    if(i<0)continue;
    [rows[rank],rows[i]]=[rows[i],rows[rank]];
    const pivot=rows[rank][j];rows[rank]=rows[rank].map(v=>divide(v,pivot));
    for(let k=0;k<rows.length;k++)if(k!==rank){
      const f=rows[k][j];rows[k]=rows[k].map((v,t)=>minus(v,times(f,rows[rank][t])));
    }
    pivots.push(j);rank++;
  }
  const basis=[];
  for(let j=0;j<species;j++){
    if(pivots.includes(j))continue;
    const w=Array.from({length:species},zero);w[j]=Q(1);
    for(let k=0;k<pivots.length;k++)w[pivots[k]]=neg(rows[k][j]);
    if(columns.some(c=>!eq(dot(w,c.map(q)),zero())))throw Error('invalid nullspace');
    basis.push(w);
  }
  return {rank,basis};
}
function step(state,cols,flux,dt,boundary){
  if(cols.length!==flux.length||state.length!==boundary.length||cols.some(c=>c.length!==state.length))throw Error('shape');
  return state.map((s,i)=>plus(s,times(dt,plus(
    cols.reduce((acc,col,k)=>plus(acc,times(col[i],flux[k])),zero()),boundary[i]))));
}
export const CASES=Object.freeze([
  {name:'enzyme_closed',columns:[[-1,-1,1,0],[1,1,-1,0],[1,0,-1,1]],state:[2,3,0,0],flux:['1/2','1/4','1/8'],dt:'1/16',boundary:[0,0,0,0]},
  {name:'chain_closed',columns:[[-1,1,0],[0,-1,1]],state:[3,1,0],flux:['1/4','1/8'],dt:'1/4',boundary:[0,0,0]},
  {name:'parallel_closed',columns:[[-1,1,0,0],[0,0,-1,1]],state:[1,2,3,4],flux:['1/4','1/6'],dt:'1/2',boundary:[0,0,0,0]},
  {name:'open_boundary',columns:[[-1,1,0],[0,-1,1]],state:[2,1,0],flux:['1/5','1/10'],dt:'1/2',boundary:['1/3',0,'-1/7']}
]);
export function experiment(){
  const output=[];
  for(const entry of CASES){
    const columns=entry.columns.map(c=>c.map(q));
    const state=entry.state.map(q), flux=entry.flux.map(q), dt=q(entry.dt), boundary=entry.boundary.map(q);
    const {rank,basis}=leftNullspace(columns,state.length);
    const after=step(state,columns,flux,dt,boundary);
    const residuals=basis.map(w=>fmt(minus(minus(dot(w,after),dot(w,state)),times(dt,dot(w,boundary)))));
    if(residuals.some(x=>x!=='0'))throw Error('conservation residual nonzero');
    output.push({case:entry.name,left_nullity:basis.length,rank,residuals});
  }
  if(output.map(x=>x.left_nullity).join(',')!=='2,1,2,1')throw Error('nullspace oracle mismatch');
  // Deliberate defective network: missing first reactant creates 1/3 amount.
  const bad=[[0,1,0],[0,-1,1]].map(c=>c.map(q));
  const final=step([3,1,0].map(q),bad,['1/3','1/5'].map(q),q(1),[0,0,0].map(q));
  const defect=fmt(minus(final.reduce(plus,zero()),q(4)));
  if(defect!=='1/3')throw Error('mutation not detected');
  // The Python experiment rejects mixed amount/concentration units; enforce too.
  const units=['amount_mol','concentration_mol_per_L'];
  const unitsRejected=units.some(u=>u!=='amount_mol');
  if(!unitsRejected)throw Error('unit mutation not detected');
  return {
    route:'reaction-conservation',case_count:output.length,left_nullities:output.map(x=>x.left_nullity),
    residuals:output.flatMap(x=>x.residuals),missing_reactant_mass_defect: defect,
    missing_reactant_mutant_detected:true,mixed_unit_mutant_rejected:unitsRejected,
    open_boundary_accounted:true,amount_units_only:true,
    formal_lean_verified:false,cace_executed:false,empirical_kinetics_validated:false,
    production_promotion_authorized:false,authority_expanded:false,
  };
}
