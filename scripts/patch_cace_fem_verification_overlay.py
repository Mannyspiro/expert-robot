#!/usr/bin/env python3
"""Apply a fail-closed verification-only overlay to a pinned *local* CACE clone.

No remote writes, no modifications to CACE numerical assembly or solvers.
Applies only to specific class.verify implementations after SHA256 pin.
The new pipeline gate can certify only the exactly defined Poisson test fixture;
it must FAIL closed for unbound or generic PDE error claims.
"""
import argparse,ast,hashlib,py_compile
from pathlib import Path

ORIGINAL_SHA="73742096c73386f83727841ac7eb6efacfebef11ce8ab24b3f4a03bf682a74c1"

PATCHES={
"AlgebraicResidual":'''    def verify(self,inputs,params,outputs,ctx):
        # Reconstruct from A, b, u rather than trusting a finite output scalar.
        try:
            A=_dense_from_csr(inputs["system"]["matrix"])
            b=np.asarray(inputs["system"]["rhs"],dtype=float)
            u=np.asarray(inputs["solution"]["interior"],dtype=float)
            r=A@u-b
            actual=float(np.linalg.norm(r,np.inf)) if r.size else 0.0
            reported=float(outputs["residual_inf"])
            reported_vec=np.asarray(outputs["residual"],dtype=float)
            tolerance=1e-10
            ok=(np.all(np.isfinite(A)) and np.all(np.isfinite(b))
                and np.all(np.isfinite(u)) and np.all(np.isfinite(r))
                and math.isfinite(reported) and reported>=0
                and reported_vec.shape==r.shape and np.all(np.isfinite(reported_vec))
                and np.allclose(reported_vec,r,rtol=1e-11,atol=1e-12)
                and abs(reported-actual)<=1e-12*max(1.,actual)
                and actual<=tolerance)
        except (ValueError,TypeError,KeyError,IndexError,OverflowError,ZeroDivisionError):
            ok=False;actual=math.inf
        return [VerificationRecord("residual-recomputed-and-bounded",EvidenceKind.NUMERICAL,
            "independently recompute A u - b and require strict residual tolerance",
            VerificationState.PASS if ok else VerificationState.FAIL,
            "independent algebraic residual replay, fixed 1e-10 threshold",
            {"residual_inf":actual,"tolerance":1e-10})]
''',
"AposterioriEstimator1D":'''    def verify(self,inputs,params,outputs,ctx):
        # Well-formedness AND recomputation; NOT a general guaranteed PDE bound.
        try:
            x=np.asarray(inputs["mesh"]["vertices"],dtype=float)
            u=np.asarray(inputs["solution"]["values"],dtype=float)
            reported=outputs["estimator"]
            local=np.asarray(reported["element_eta"],dtype=float)
            total=float(reported["eta"])
            h=np.diff(x)
            if (len(x)<2 or len(u)!=len(x) or local.shape!=(len(h),)
                or np.any(h<=0) or not np.all(np.isfinite(x))
                or not np.all(np.isfinite(u)) or not np.all(np.isfinite(local))
                or not math.isfinite(total)):
                raise ValueError("invalid estimator or mesh")
            slopes=np.diff(u)/h
            jumps=np.zeros(len(x))
            for k in range(1,len(x)-1):
                jumps[k]=slopes[k]-slopes[k-1]
            expected=np.array([math.sqrt(float(hk**3+0.5*hk*(
                jumps[k]**2+jumps[k+1]**2))) for k,hk in enumerate(h)])
            actual=math.sqrt(float(np.sum(expected**2)))
            ok=(np.all(local>=0) and total>=0
                and np.allclose(local,expected,atol=1e-12,rtol=1e-11)
                and math.isclose(total,actual,rel_tol=1e-11,abs_tol=1e-12))
        except (ValueError,TypeError,KeyError,IndexError,OverflowError,ZeroDivisionError):
            ok=False;actual=math.inf
        return [VerificationRecord("estimator-recomputed-not-certified",EvidenceKind.NUMERICAL,
            "estimator matches its formula; this is NOT a proven a posteriori bound",
            VerificationState.PASS if ok else VerificationState.FAIL,
            "independent mesh/solution/eta recomputation, no reliability theorem",
            {"recomputed_eta":actual,"general_pde_bound_certified":False})]
''',
"PipelineCertificate":'''    def verify(self,inputs,params,outputs,ctx):
        # Exact benchmark-only gate. Do not trust a self-described interval,
        # finite number, claimed theorem flag, or unbound output summary.
        # Benchmark identity is bound externally by the CI, immutable CACE SHA,
        # 1D f=1 assembly and analytic Dirichlet solution checks below.
        try:
            from fractions import Fraction as Q
            tol=float(params["residual_tolerance"])
            if not math.isfinite(tol) or tol<0 or tol>1e-10:
                raise ValueError("unqualified tolerance")
            if inputs.get("benchmark_model_id")!="pinned-poisson-1d-f1-dirichlet0-v1":
                raise ValueError("no qualified benchmark identity")
            x0=inputs["refined_mesh"]["vertices"]
            y0=inputs["solution"]["values"]
            if len(x0)<2 or len(y0)!=len(x0):
                raise ValueError("invalid mesh or solution")
            x=[Q.from_float(float(v)) for v in x0]
            y=[Q.from_float(float(v)) for v in y0]
            if x[0]!=0 or x[-1]!=1 or y[0]!=0 or y[-1]!=0:
                raise ValueError("benchmark Dirichlet boundaries differ")
            h=[x[i+1]-x[i] for i in range(len(x)-1)]
            if any(step<=0 for step in h):
                raise ValueError("nonpositive mesh")
            # Independently reassemble the exact interior P1 stiffness/load
            # for the pinned -u''=1 analytical benchmark using rationals.
            dofs=len(x)-2
            A=[[Q(0) for _ in range(dofs)] for _ in range(dofs)]
            b=[Q(0) for _ in range(dofs)]
            for i in range(1,len(x)-1):
                b[i-1]=(h[i-1]+h[i])/2
                for j in range(1,len(x)-1):
                    A[i-1][j-1]=(
                        (1/h[i-1]+1/h[i]) if i==j else (
                        (-1/h[i-1]) if j==i-1 else (
                        (-1/h[i]) if j==i+1 else Q(0))))
            if "system" not in inputs:
                raise ValueError("missing source assembly")
            matrix=np.asarray(_dense_from_csr(inputs["system"]["matrix"]),float)
            rhs=np.asarray(inputs["system"]["rhs"],float)
            if matrix.shape!=(dofs,dofs) or rhs.shape!=(dofs,):
                raise ValueError("wrong source assembly shape")
            if not np.all(np.isfinite(matrix)) or not np.all(np.isfinite(rhs)):
                raise ValueError("nonfinite source assembly")
            for i in range(dofs):
                if abs(float(b[i])-float(rhs[i]))>1e-11:
                    raise ValueError("benchmark load differs")
                for j in range(dofs):
                    if abs(float(A[i][j])-float(matrix[i,j]))>1e-10:
                        raise ValueError("benchmark stiffness differs")
            residual=max((abs(sum((A[i][j]*y[j+1] for j in range(dofs)),Q(0))-b[i])
                          for i in range(dofs)),default=Q(0))
            r_report=float(inputs["residual_inf"])
            if (not math.isfinite(r_report) or r_report<0
                or residual>Q.from_float(tol)
                or abs(float(residual)-r_report)>1e-11):
                raise ValueError("unqualified residual")
            # Exact P1 energy-error identity (for this analytic benchmark):
            # ||u-u_h||_E^2 = sum(h^3/12) +
            #                  sum((delta_i-delta_{i+1})^2/h).
            # delta_i = (reported FEM nodal value) - exact analytic nodal.
            delta=[y[i]-x[i]*(1-x[i])/2 for i in range(len(x))]
            energy2=sum((step**3/12 for step in h),Q(0))+sum(
                ((delta[i+1]-delta[i])**2/h[i] for i in range(len(h))),Q(0))
            lo0,hi0=inputs["error_interval"]
            lo=Q.from_float(float(lo0));hi=Q.from_float(float(hi0))
            # A vacuously broad [0, huge] interval is not a useful
            # quantitative certificate. Require a narrow rational bracket.
            if (lo<0 or hi<lo or hi-lo>Q(1,10**10)
                or lo*lo>energy2 or hi*hi<energy2):
                raise ValueError("unqualified, reversed or overly broad error interval")
            s=outputs["certificate_summary"]
            if (s["residual_pass"] is not True
                or abs(float(s["residual_inf"])-r_report)>1e-11
                or float(s["residual_tolerance"])!=tol
                or list(s["benchmark_energy_error_interval"])!=list(map(float,[lo0,hi0]))
                or s["refined_vertices"]!=len(x)):
                raise ValueError("summary does not bind source inputs")
            # A finite/nonnegative reported eta alone is not acceptable:
            # separately reconstruct local indicators from trusted mesh/solution.
            erecord=AposterioriEstimator1D.verify(None,
                {"mesh":inputs["refined_mesh"],"solution":inputs["solution"]},
                {},{"estimator":inputs["estimator"]},None)
            if len(erecord)!=1 or erecord[0].state!=VerificationState.PASS:
                raise ValueError("estimator not independently reconstructed")
            eta=float(inputs["estimator"]["eta"])
            if not math.isfinite(eta) or eta<0 or abs(float(s["estimator"])-eta)>1e-11:
                raise ValueError("estimator field inconsistent")
            ok=True
            detail={"exact_squared_energy_error":str(energy2),
                    "benchmark_only":True,"general_pde_bound_certified":False}
        except (ValueError,TypeError,KeyError,IndexError,OverflowError,ZeroDivisionError):
            ok=False
            detail={"benchmark_only":True,"general_pde_bound_certified":False}
        return [VerificationRecord("analytic-poisson-interval-gate",EvidenceKind.NUMERICAL,
            "interval contains independently computed analytic 1D P1 energy error",
            VerificationState.PASS if ok else VerificationState.FAIL,
            "source-bound exact Fraction error identity, never general PDE certification",
            detail)]
'''
}

def apply(path):
    data=path.read_bytes()
    if hashlib.sha256(data).hexdigest()!=ORIGINAL_SHA:
        raise ValueError("refuse unpinned or previously modified CACE FEM")
    source=data.decode("utf-8")
    lines=source.splitlines(keepends=True)
    tree=ast.parse(source)
    patches=[]
    for node in tree.body:
        if isinstance(node,ast.ClassDef) and node.name in PATCHES:
            methods=[m for m in node.body if isinstance(m,ast.FunctionDef) and m.name=="verify"]
            if len(methods)!=1:
                raise ValueError("unexpected verification API")
            m=methods[0]
            patches.append((m.lineno-1,m.end_lineno,PATCHES[node.name]))
    if len(patches)!=len(PATCHES):
        raise ValueError("missing target CACE modules")
    for start,end,replacement in sorted(patches,reverse=True):
        lines[start:end]=[replacement]
    updated="".join(lines)
    ast.parse(updated)
    path.write_text(updated,encoding="utf-8")
    py_compile.compile(str(path),doraise=True)
    return hashlib.sha256(updated.encode()).hexdigest()

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--cace-repo",type=Path,required=True)
    args=p.parse_args()
    path=args.cace_repo/"cace_studio/modules/fem.py"
    sha=apply(path)
    print({"patched_local_file_sha256":sha,"native_methods_hardened":sorted(PATCHES),
           "production_modified":False,"authority_expanded":False})
