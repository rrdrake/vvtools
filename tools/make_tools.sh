#!/bin/bash

if ([ -z $NETCDF_ROOT ]); then 
    echo "missing NETCDF_ROOT - suggest running set_toolchain.sh first to load modules"
    exit 1
fi
if ([ -z $SEMS_PYTHON_INCLUDE_PATH ]); then 
    echo "missing SEMS_PYTHON_INCLUDE_PATH - suggest running set_toolchain.sh first to load modules"
    exit 1
fi

export BUILD_DIR=build_tools
mkdir $BUILD_DIR
cd $BUILD_DIR
cp -r ../exolib/cbind .
cp -r ../exolib/exomod .

echo " building libexoIIv2c.so "
cd cbind/src
gcc -fPIC -c -g -O2  -I../include -I${NETCDF_ROOT}/include *.c
gcc -shared -g -o ../../libexoIIv2c.so exopen.o exgset.o expnv.o exgebi.o expvpc.o exgelb.o expvv.o exgev.o expeat.o exgatn.o expnvv.o exupda.o exgcns.o expmp.o expmap.o exgnnm.o exgnmap.o expvan.o expss.o exgvnm.o expvar.o expnstt.o exgoea.o expnams.o expsetd.o expp.o exgotv.o exgnm.o exgnam.o exgpn.o exgvtt.o exgcon.o exinq.o expvarparam.o exgcor.o exgnsvid.o exgvarnam.o expsetp.o exgtt.o expini.o expenm.o expns.o exgtim.o exgssd.o expfrm.o expvarnam.o expatt.o exgqa.o exgelc.o exgnsv.o expsstt.o expem.o exgids.o expinix.o expgv.o exgnstt.o exppem.o expsp.o exgsnl.o expnsd.o exgevt.o excn2s.o exgnams.o exgsetd.o exggvt.o expconn.o exppa.o exgnvv.o exgeat.o exgsetp.o exgmap.o exgvartab.o expattp.o expblk.o expidm.o exgnv.o expssv.o exgvan.o expinf.o expnp.o expvpax.o expvartab.o ex_utils.o exgvar.o exclos.o exgvv.o exgsstt.o expvp.o exgssi.o expcab.o expvpa.o exginix.o exgvarnams.o expcset.o exgmp.o exgvart.o expean.o exgini.o exgenm.o expev.o exgfrm.o exgss.o exgatt.o ex_conv.o exgconn.o exgnvid.o expcss.o excre.o expset.o exgattp.o expclb.o expelb.o expvarnams.o expoatt.o exgns.o exgpem.o expnm.o exgnsd.o exppn.o expatn.o expcns.o exgcset.o exgp.o exptt.o exgem.o expnnm.o exgssn.o exgblk.o exgidm.o expvnm.o expqa.o exgssv.o exggv.o exginf.o expoea.o exgatm.o exgsp.o expnam.o expvtt.o expcon.o expcor.o exgpa.o expssd.o exptim.o exgean.o excopy.o expnmap.o exgnvt.o exgoatt.o exgvarparam.o expelc.o exgnp.o exopts.o expnsv.o exerr.o exgvid.o exgvp.o exgevid.o exgssvid.o exgssc.o exgcss.o exgnsi.o  -Xlinker -rpath ${NETCDF_ROOT}/lib/libnetcdf.so

echo " building exomod_lib.so "
cd ../../exomod
gcc -fPIC -O2 -c -o exomod.o exomod.c -I../cbind/include/ -I${NETCDF_ROOT}/include
gcc -fPIC -O2 -c -o exomod_lib.o exomod_lib.c -I${SEMS_PYTHON_INCLUDE_PATH}/python2.7
gcc -shared -g -o ../../exomod_lib.so exomod_lib.o exomod.o -Xlinker ../libexoIIv2c.so ${NETCDF_ROOT}/lib/libnetcdf.so

cd ../..

