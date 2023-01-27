# Disable core dumps
ulimit -c 0

# >>> conda initialize >>>
# !! Contents within this block are managed by 'conda init' !!
__conda_setup="$('/softs/rh7/conda/4.9.0/bin/conda' 'shell.bash' 'hook' 2> /dev/null)"
if [ $? -eq 0 ]; then
    eval "$__conda_setup"
else
    if [ -f "/softs/rh7/conda/4.9.0/etc/profile.d/conda.sh" ]; then
        . "/softs/rh7/conda/4.9.0/etc/profile.d/conda.sh"
    else
        export PATH="/softs/rh7/conda/4.9.0/bin:$PATH"
    fi
fi
unset __conda_setup
# <<< conda initialize <<<


###### Aliases
#
module() {  eval $($LMOD_CMD bash "$@") && eval $(${LMOD_SETTARG_CMD:-:} -s sh) }

alias node='qsub -IX -l select=1:ncpus=8:mem=32000mb -l walltime=10:00:00'
alias node_big='qsub -IX -l select=1:ncpus=16:mem=64000mb -l walltime=10:00:00'
alias proxy="source ~/.proxy.sh"

conf_geco() {
  echo "Configuring Geco"
  cmake -DCMAKE_CXX_COMPILER=$(which g++) \
        -DCMAKE_C_COMPILER=$(which gcc) \
        -DPYTHON_EXECUTABLE=$(which python) \
        -DEIGEN3_INCLUDE_DIR=$EIGENHOME/include/eigen3 \
        -DNETCDF_INCLUDE_DIR=$NETCDFHOME/include \
        -DBOOST_ROOT=$BOOSTHOME \
        -DGSL_ROOT_DIR=$GSLHOME \
        -DECCODES_ROOT_DIR=${ECCODESHOME} \
        -DBUILD_PYTHON=ON \
        -Dpybind11_DIR=${PY_PYBIND11HOME} \
        -DBUILD_SHARED_LIBS=ON \
        -DBUILD_UNITTEST=ON \
        -DBUILD_DOC=OFF \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_INSTALL_PREFIX=/home/ad/berthiv/.local \
        ..
}

conf_gecomain() {
  echo "Configuring Geco Main"
  cmake -DCMAKE_CXX_COMPILER=$(which g++) \
        -DCMAKE_C_COMPILER=$(which gcc) \
        -DPYTHON_EXECUTABLE=$(which python) \
        -DCMAKE_BUILD_TYPE=Release \
        -DEIGEN3_INCLUDE_DIR=$EIGENHOME/include/eigen3 \
        -DNETCDF_INCLUDE_DIR=$NETCDFHOME/include \
        -DBOOST_ROOT=$BOOSTHOME \
        -DGSL_ROOT_DIR=$GSLHOME \
        -DYAML_CPP_BUILD_TESTS=off \
        -DECCODES_ROOT_DIR=${ECCODESHOME} \
        -DBUILD_PYTHON=ON \
        -DBUILD_SHARED_LIBS=ON \
        -DBUILD_UNITTEST=ON \
        -DBUILD_DOC=ON \
        ..
}

conf_bang() {
  echo "Configuring BA-NG"
  cmake -DCMAKE_BUILD_TYPE=Debug \
        -DnetCDFCxx_DIR=/home/ad/berthiv/scratch/.conda/envs/bang/lib/cmake/netCDF/ \
        -DNETCDF_PATH=${NETCDFHOME} \
        ..
}

load_geco() {
  proxy
  module load git-lfs
  module load boost/1.65.1
  module load cmake/3.11.3
  module load doxygen/1.8.13
  module load ecCodes/2.7.3
  module load eigen/3.3.2
  module load gcc/7.3.0
  module load llvm/10.0.0
  module load gsl/2.3
  module load netcdf/4.4.1
  module load python/3.7.2
  module load pybind11/2.9.0
  module load googletest/1.11.0_gcc-7.3.0
  module load lcov/1.12
}

load_bangpy() {
  proxy
  module purge
  module load boost/1.73.0
  module load cmake/3.11.3
  module load python/3.8.4
  module swap gcc/10.1.0 gcc/10.2.0
  module load eigen/3.3.2
  module load llvm/10.0.0
  module load netcdf/4.7.4
  module load git/2.34.1
  module load git-lfs/3.0.2
  module load ecCodes/2.23.0
  export VIRTUALENVWRAPPER_PYTHON=/softs/rh7/spack_install/linux-centos7-x86_64/gcc-10.2.0/python-3.8.4-quigmdjvagbs5t4qqlb7yhmgugpa4q5s/bin/python3
  source /softs/rh7/spack_install/linux-centos7-x86_64/gcc-10.2.0/python-3.8.4-quigmdjvagbs5t4qqlb7yhmgugpa4q5s/bin/virtualenvwrapper.sh
  workon bang
}


load_bang() {
  proxy
  module purge
  module load boost/1.73.0
  module swap gcc/10.1.0 gcc/10.2.0
  module load gdb/.11.2__gcc-10.2.0_eukrg4i
  module load eigen/3.3.2
  module load llvm/10.0.0
  module load netcdf/4.7.4
  module load git/2.34.1
  module load git-lfs/3.0.2
  module load ecCodes/2.23.0
  module load latex/2019
  module unload python
  module load conda/4.9.0
  conda activate bang
  cd scratch/bang/sources
}

load_sas() {
  module load cmake/3.11.3 
  module load boost/1.65.1 
  module load gcc/7.3.0 
  module load python/3.6.5 
  module load latex/2019 
}
