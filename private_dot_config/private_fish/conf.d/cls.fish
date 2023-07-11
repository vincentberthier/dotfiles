## CLS specific aliases
set host (hostname)

function iscmd
    command -v >&- "$argv"
end

alias quota="pxquota space status"
#Module control (module avail, module load, etc.)
function module 
    eval ($LMOD_CMD bash "$argv") 
    # eval ({$LMOD_SETTARG_CMD:-:} -s sh)
end

# Colorisze ls
function ls --description "ls specific to the current machine"
   if [ (hostname) = "px-1021" ]
       colorls --gs --sd --dark $argv
    else
        lsd -h $argv
    end
end

# Netcdf
function nchead ()
    if [ -f $1 ]
        ncdump -h $1 | less
    else
        echo "'$1' does not exist."
    end
end

if [ $host = "px-2091" ]
    alias valid_netcdf="/data/MPC_S3/LandBranches/Sentinel3_ContinuousIntegrationData/workshop/validation_tools/src/valid_netcdf_product.py"
else
    alias valid_netcdf="/data/PDAP_JCS/validation_tools/src/valid_netcdf_product.py"
end

## CLS specific exports
set -Ux TZ "Europe/Paris"

set -Ux PYTHONPATH "/home/vberthier/.local/bin:$PYTHONPATH"

if [ $host = "px-2091" ]
  set -x COTS_ROOT /data/MPC_S3/LandBranches/Sentinel3_ContinuousIntegrationData/COTS_V2
  set -x JPEG_PATH $COTS_ROOT/JPEG/V1.2.1/lib/
  set -x HDF5_PATH $COTS_ROOT/HDF5/V1.8.9/lib/
  set -x PROJ_PATH $COTS_ROOT/PROJ/V4.8.0/lib/
  set -x CPPEOCFI_PATH $COTS_ROOT/CPPEOCFI/V4.22/libraries/LINUX64_LEGACY/
  set -x NETCDF_PATH $COTS_ROOT/NETCDF/V4.2/lib/
  set -x XERCESC_PATH $COTS_ROOT/XERCESC/V2.8.0/lib/
  set -x JPEG_PATH $COTS_ROOT/JPEG/V1.2.1/lib/
  set -x OPENJPEG_PATH $COTS_ROOT/OpenJPEG/V2.0.0/lib/
  set -x PNG_PATH $COTS_ROOT/PNG/V1.5.11/lib/
  set -x GRIB_PATH $COTS_ROOT/GRIB/V1.9.18/
  set -x LD_LIBRARY_PATH "$HDF5_PATH:$PROJ_PATH:$CPPEOCFI_PATH:$NETCDF_PATH:$XERCESC_PATH:$JPEG_PATH:$OPENJPEG_PATH:$PNG_PATH:$LD_LIBRARY_PATH"
end
