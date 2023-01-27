### CLS Specifics
case $DISPLAY:$XAUTHORITY in
  :*:?*)
    # DISPLAY is set and points to a local display, and XAUTHORITY is
    # set, so merge the contents of `$XAUTHORITY` into ~/.Xauthority.
    XAUTHORITY=~/.Xauthority xauth merge "$XAUTHORITY";;
esac

######## Conda initilization
# >>> conda initialize >>>
# !! Contents within this block are managed by 'conda init' !!
__conda_setup="$('/homelocal/anaconda/conda/bin/conda' 'shell.bash' 'hook' 2> /dev/null)"
if [ $? -eq 0 ]; then
 eval "$__conda_setup"
else
 if [ -f "/homelocal/anaconda/conda/etc/profile.d/conda.sh" ]; then
     . "/homelocal/anaconda/conda/etc/profile.d/conda.sh"
 else
     export PATH="/homelocal/anaconda/conda/bin:$PATH"
 fi
fi
unset __conda_setup
# <<< conda initialize <<<
conda deactivate

export CONDA=/homelocal/vberthier/.conda/envs/dev

host=`hostname`

if [[ $host == "px-2131" ]]; then
  export PYTHONPATH=$PYTHONPATH:/homelocal/vberthier/.conda/envs/dev/lib/python3.8/site-packages:/home/vberthier/Code/GECO_main/validation/utilities/WxPlot12-2.1/src:/home/vberthier/Code/geco/build/python:/home/vberthier/Code/extract_ba/build/python:/home/vberthier/Code/extract_ba/third_party/julian-0.1/:/home/vberthier/.local/bin
elif [[ $host == "px-2091" ]]; then

  export COTS_ROOT=/data/MPC_S3/LandBranches/Sentinel3_ContinuousIntegrationData/COTS_V2
  export JPEG_PATH=${COTS_ROOT}/JPEG/V1.2.1/lib/
  export HDF5_PATH=${COTS_ROOT}/HDF5/V1.8.9/lib/
  export PROJ_PATH=${COTS_ROOT}/PROJ/V4.8.0/lib/
  export CPPEOCFI_PATH=\$COTS_ROOT/CPPEOCFI/V4.22/libraries/LINUX64_LEGACY/
  export NETCDF_PATH=${COTS_ROOT}/NETCDF/V4.2/lib/
  export XERCESC_PATH=${COTS_ROOT}/XERCESC/V2.8.0/lib/
  export JPEG_PATH=${COTS_ROOT}/JPEG/V1.2.1/lib/
  export OPENJPEG_PATH=${COTS_ROOT}/OpenJPEG/V2.0.0/lib/
  export PNG_PATH=${COTS_ROOT}/PNG/V1.5.11/lib/
  export GRIB_PATH=${COTS_ROOT}/GRIB/V1.9.18/
  export LD_LIBRARY_PATH=${HDF5_PATH}:${PROJ_PATH}:${CPPEOCFI_PATH}:${NETCDF_PATH}:${XERCESC_PATH}:${JPEG_PATH}:${OPENJPEG_PATH}:${PNG_PATH}:${LD_LIBRARY_PATH}:/data/MPC_S3/vberthier/s3_ipf_l1/bin/lib
fi

#### Aliases
#
alias quota="pxquota space status"
module() {  eval $($LMOD_CMD bash "$@") && eval $(${LMOD_SETTARG_CMD:-:} -s sh) }

host=`hostname`

if [[ $host == "px-2131" ]]; then
  dev() {
    conda activate /homelocal/vberthier/.conda/envs/dev
  }

  proto() {
    conda activate /homelocal/vberthier/.conda/envs/proto
  }

  dev2() {
    conda activate /homelocal/vberthier/.conda/envs/dev2
  }

  alias valid_netcdf="/data/PDAP_JCS/validation_tools/src/valid_netcdf_product.py"

elif [[ $host == "px-2091" ]]; then

  alias valid_netcdf="/data/MPC_S3/LandBranches/Sentinel3_ContinuousIntegrationData/workshop/validation_tools/src/valid_netcdf_product.py"
fi
