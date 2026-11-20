"""Clocked 2-bond tensor tile for a finite, simulated environment."""
from dataclasses import dataclass
from itertools import product

LIMIT=2**15
ZERO=(0,0)
ONE=(1,0)
IDENTITY=((ONE,ZERO),(ZERO,ONE))

def add(a,b):
    return (a[0]+b[0],a[1]+b[1])

def mul(a,b):
    return (a[0]*b[0]-a[1]*b[1],a[0]*b[1]+a[1]*b[0])

def check(value):
    if type(value) is not tuple or len(value)!=2 or any(type(n) is not int for n in value):
        raise ValueError('A scalar is a pair of signed integers')
    if any(not -LIMIT<=n<LIMIT for n in value):
        raise OverflowError('Signed 16-bit component overflow')
    return value

def validate_matrix(matrix):
    if type(matrix) is not tuple or len(matrix)!=2 or any(type(row) is not tuple or len(row)!=2 for row in matrix):
        raise ValueError('Only 2 by 2 bond matrices are supported')
    for row in matrix:
        for element in row: check(element)

def pair_from(values):
    def pack(value):
        real, imag = complex(value).real, complex(value).imag
        if not real.is_integer() or not imag.is_integer():
            raise ValueError('Only Gaussian integers can be packed')
        return check((int(real), int(imag)))
    matrix = tuple(tuple(pack(value) for value in row) for row in values)
    validate_matrix(matrix)
    return matrix

@dataclass(frozen=True)
class Boundary:
    mode: str
    left: tuple | None = None
    right: tuple | None = None

    def validate(self):
        if self.mode=='open':
            for vec in self.left,self.right:
                if type(vec) is not tuple or len(vec)!=2:
                    raise ValueError('Open boundary needs two explicit endpoint vectors')
                for element in vec:check(element)
        elif self.mode!='loop' or self.left is not None or self.right is not None:
            raise ValueError('Loop semantics identify indices and take the trace')

class Tile:
    def __init__(self):
        self.cycle=0
        self.state=IDENTITY
        self.trace=[]

    def contract(self,matrix):
        validate_matrix(matrix)
        original=self.state
        accum=[[ZERO,ZERO],[ZERO,ZERO]]
        pending=[]
        for k in range(2):
            for i,j in product(range(2),repeat=2):
                accum[i][j]=add(accum[i][j],mul(original[i][k],matrix[k][j]))
            self.cycle+=1
            pending.append({'clock':self.cycle,'instruction':'CONTRACT','bond_index':k,
                            'lanes':[list(a) for row in accum for a in row],
                            'real_multiplications':16})
        try:
            new=tuple(tuple(check(a) for a in row) for row in accum)
        except OverflowError:
            pending[-1]['fault']='overflow'
            self.trace.extend(pending)
            raise
        self.state=new
        pending[-1]['writeback']=True
        self.trace.extend(pending)
        return new

    def read(self,boundary):
        boundary.validate()
        self.cycle+=1
        if boundary.mode=='loop':
            scalar=add(self.state[0][0],self.state[1][1])
        else:
            scalar=ZERO
            for i,j in product(range(2),repeat=2):
                scalar=add(scalar,mul(mul(boundary.left[i],self.state[i][j]),boundary.right[j]))
        try:check(scalar)
        except OverflowError:
            self.trace.append({'clock':self.cycle,'instruction':'READ','mode':boundary.mode,'fault':'overflow'})
            raise
        self.trace.append({'clock':self.cycle,'instruction':'READ','mode':boundary.mode,'value':scalar})
        return scalar

def run(chain,boundary):
    if not 1<=len(chain)<=8: raise ValueError('Use one to eight matrices')
    boundary.validate()
    tile=Tile()
    for matrix in chain: tile.contract(matrix)
    return tile.read(boundary),tile

def oracle(chain,boundary):
    """Enumerate assignments over all leg indices instead of using matrix multiplication."""
    total=0j
    for indices in product((0,1),repeat=len(chain)+1):
        if boundary.mode=='loop' and indices[0]!=indices[-1]:continue
        path=1+0j
        if boundary.mode=='open':
            path*=complex(*boundary.left[indices[0]])*complex(*boundary.right[indices[-1]])
        for n,matrix in enumerate(chain):
            path*=complex(*matrix[indices[n]][indices[n+1]])
        total+=path
    return (int(total.real),int(total.imag))
