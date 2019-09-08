#!/bin/bash
set -e

LIST_OF_PYTHON_VERSIONS="
2.6
2.6.9
2.7
2.7.16
3.3.0
3.4.0
3.5.0
3.6.0
3.6.1
3.6.2
3.6.3
3.6.4
3.6.5
3.6.6
3.6.7
3.6.8
3.7.0
3.7.1
3.7.2
"

LIST_OF_PYTHON_VERSIONS="
2.6
2.7
3.3
3.4.0
3.5.0
3.6.0
3.6.1
3.6.2
3.6.3
3.6.4
3.6.5
3.6.6
3.6.7
3.6.8
3.7.0
3.7.1
3.7.2
"


#source ../../../set_empire_root
export PATH=${HOME}/.anaconda_python/tox_python/bin:${PATH}

conda info --envs 
#conda init bash
for FULL_VERSION in ${LIST_OF_PYTHON_VERSIONS}
do
  ENV_NAME=py`echo ${FULL_VERSION} | sed 's/\.//g'`
  echo ${FULL_VERSION}
  echo ${ENV_NAME}

  source activate ${ENV_NAME}
  python -m pytest -v simple_aprepro.py
  source deactivate

  echo "#############################################"
  echo "               DONE ${FULL_VERSION}"
  echo "#############################################"

done
