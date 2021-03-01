
from subprocess import run


# Felix likes command line, so just call it
# python do_it_all.py [-h] [-b MILLER_BOUNDS] [-l NLAYERS] [-v VACUUM] [-o OUTDIR] [-f FILES]
run(['python',  '../do_it_all.py', '-b', '10', '-l', '6', '-v', '3', '-o', './results', '-f', '.'])