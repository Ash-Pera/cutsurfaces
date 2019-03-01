from make_surface import *
from read_icsd import icsd_cif_a
from pylada.crystal import write, supercell
from numpy import array,sum, diag, arange, transpose, float64
from numpy.linalg import inv
import os
import pickle
from glob import iglob
from mpi4py import MPI
import argparse
from sys import version_info, stdout


# Initial MPI calls
comm = MPI.COMM_WORLD
master = 0
n_proc = comm.Get_size()
rank = comm.Get_rank()

########################################################

#### INPUTS

miller_bounds=1
nlayers=3
vacuum=20
outdir = "outdir"
files = list(iglob("./*/*cif"))

if rank==master:

    parser = argparse.ArgumentParser()
    parser.add_argument("-b","--miller_bounds",dest="miller_bounds",type=int, default=3, help="Maximum index of the combinations of miller indices to try")
    parser.add_argument("-l","--nlayers",dest="nlayers", type=int, default=3, help="Number of layers for the output")
    parser.add_argument("-v","--vacuum",dest="vacuum", type=float, default=20, help="Size of vacuum between slabs in angstroms")
    parser.add_argument("-o","--outdir",dest="outdir", type=str, default="outdir", help="Output directory")
    parser.add_argument("-f","--files",dest="files", type=str, default=".", help="Folder to look for the cif files. ex: ./*/*cif")

    options = parser.parse_args()
        
    miller_bounds=options.miller_bounds
    nlayers=options.nlayers
    vacuum=options.vacuum
    outdir=options.outdir
    files =list(iglob(options.files))

    os.system("mkdir -p " + outdir)

    print("Slabs will be cut for the following %d structures:"%len(files))
    for f in files:
        print(f)
    print("---------------------------------------------")
    stdout.flush()

miller_bounds, nlayers, vacuum, outdir, files = comm.bcast((miller_bounds, nlayers, vacuum, outdir, files))

def load_balance(n_tasks):
# Defines the interval each cores needs to compute
    
    n_jobs = n_tasks//n_proc
    balance = n_tasks%n_proc

    if (rank < balance): 
        i_init = rank*(n_jobs+1)+1
        i_fin = (rank+1)*(n_jobs+1)
    else:
        i_init = balance*(n_jobs+1) + (rank-balance)*(n_jobs)+1
        i_fin = balance*(n_jobs+1) + (rank-balance+1)*(n_jobs)

    return range(i_init-1, i_fin)


for f in load_balance(len(files)):

    print("%s on core %d: STARTING"%(files[f], rank))
    stdout.flush()

    bulk = icsd_cif_a(files[f])
    
    space_group = bulk.group
    
    charge = dict([(a.type, a.ox) for a in bulk])
    # charge={'Al':3.,'P':-3.}
    
    ############# END INPUTS
    
    dir_cell=transpose(bulk.cell)
    rec_cell=2*pi*transpose(inv(dir_cell))
    
    with open('symmetries.pickle','rb') as handle:
        if version_info[0] >= 3:
            syms=pickle.load(handle, encoding='latin1')[space_group]
        else:
            syms=pickle.loads(handle.read())[space_group]
    # HOW TO WRITE PICKLE
    #with open('symmetries.pickle','wb') as handle:
    #    pickle.dump(data,handle)
    
    
    #############################################
    
    def are_eq(m1,m2,rec_cell=rec_cell):
        m1=dot(array(m1),rec_cell)
        m2=dot(array(m2),rec_cell)
        result=False
        for sym in syms:
            x=dot(sym,m1)
            if sqrt(dot(x-m2,x-m2))<1e-3:
                result=True
                break
        return result
    
    #############################################
    
    def make_trials(bound):
        trials=[array([h,k,l]) for h in range(bound,-bound-1,-1) for k in range(bound,-bound-1,-1) for l in range
    (bound,-bound-1,-1)]
        indices=[]
        for i in range(len(trials)):
            if i not in indices:
                for j in range(len(trials)):
                    distance=sqrt(dot(trials[i]+trials[j],trials[i]+trials[j]))
                    if distance==0.:indices.append(j)
                    
            for y in range(bound-1):
                if all([x==int(x) for x in trials[i]/float(y+2)]): indices.append(i)
    
        new_trials=[trials[i] for i in range(len(trials)) if i not in indices]
    
        out = []
    
        for nt in new_trials:
            if len(out)==0:
                out.append(nt)
            elif len(out)>0:
                if not any([are_eq(nt,x) for x in out]):
                    out.append(nt)
    #    return new_trials
        return out
    #############################################
    
    trials=make_trials(miller_bounds)

    outdir_cur = outdir + "/" + "/".join(files[f].split("/")[-2:])
    outdir_cur = outdir_cur[:outdir_cur.rindex(".")]
    
    os.system("mkdir -p " + outdir_cur)

    file=open(outdir_cur + '/out.txt','w')
    
    # print("%s surface orienttions to go!" %(len(trials)))
    
    for miller in trials:
    
        slab=make_surface(structure=bulk,miller=miller,nlayers=nlayers,vacuum=vacuum,acc=10)
        # print("Done with the supercell")
        
        slab = minimize_broken_bonds(bulk=bulk,slab=slab,vacuum=vacuum,charge=charge,minimize_total=True)
        # print("Done with the supercell construction, now shaping it")
        
        cell=transpose(slab.cell)
        cell[2][0]=0.
        cell[2][1]=0.
        slab.cell=transpose(cell)
        r=diag([1,1,1])
        slab=supercell(slab,dot(slab.cell,r))
        
        write.poscar(structure=slab,file=outdir_cur + '/POSCAR_%s%s%s_%slay_%svac' %(miller[0],miller[1],miller[2],nlayers,vacuum),vasp5=True)
        
        file.write('% 2i  % 2i  % 2i    broken_bonds %2.4f %2.4f polar=%s\n' %(miller[0],miller[1],miller[2],count_broken_bonds(bulk=bulk,slab=slab),count_broken_bonds_per_area(bulk=bulk,slab=slab),is_polar(slab=slab,charge=charge)))
        file.flush()
    file.close()

    print("%s on core %d: DONE"%(files[f], rank))

#############################################

