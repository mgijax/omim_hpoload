#!/bin/sh
#
#  omim_hpoload.sh
###########################################################################
#
#  Purpose:
# 	This script creates a OMIM/HPO annotation load
#       input file and invokes the annotload using that input file.
#
#  Usage=omim_hpoload.sh
#
#  Env Vars:
#
#      See the configuration file
#
#  Inputs:
#
#      - Common configuration file -
#               /usr/local/mgi/live/mgiconfig/master.config.sh
#      - load configuration file - omim_hpoload.config
#      - annotation load config file - annotload.config
#      - input file - see python script header
#
#  Outputs:
#
#      - An archive file
#      - Log files defined by the environment variables ${LOG_PROC},
#        ${LOG_DIAG}, ${LOG_CUR} and ${LOG_VAL}
#      - Input file for annotload
#      - see annotload outputs
#      - Records written to the database tables
#      - Exceptions written to standard error
#      - Configuration and initialization errors are written to a log file
#        for the shell script
#
#  Exit Codes:
#
#      0:  Successful completion
#      1:  Fatal error occurred
#      2:  Non-fatal error occurred
#
#  Assumes:  Nothing
#
# History:
#
# sc	03/16/2016 - TR12267
#

cd `dirname $0`

COMMON_CONFIG=omim_hpoload.config

USAGE="Usage: omimhpo.sh"

#
#  Verify the argument(s) to the shell script.
#
if [ $# -ne 0 ]
then
    echo ${USAGE} | tee -a ${LOG}
    exit 1
fi

#
# Make sure the common configuration file exists and source it.
#
if [ -f ../${COMMON_CONFIG} ]
then
    . ../${COMMON_CONFIG}
else
    echo "Missing configuration file: ${COMMON_CONFIG}"
    exit 1
fi

#
# Initialize the log file.
#
LOG=${LOG_FILE}
rm -rf ${LOG}
touch ${LOG}

#
#  Source the DLA library functions.
#

if [ "${DLAJOBSTREAMFUNC}" != "" ]
then
    if [ -r ${DLAJOBSTREAMFUNC} ]
    then
        . ${DLAJOBSTREAMFUNC}
    else
        echo "Cannot source DLA functions script: ${DLAJOBSTREAMFUNC}" | tee -a ${LOG}
        exit 1
    fi
else
    echo "Environment variable DLAJOBSTREAMFUNC has not been defined." | tee -a ${LOG}
    exit 1
fi

#
# verify input file exists and is readable
#

if [ ! -r ${INPUT_FILE_DEFAULT} ]
then
    # set STAT for endJobStream.py
    STAT=1
    checkStatus ${STAT} "Cannot read from input file: ${INPUT_FILE_DEFAULT}"
fi

#####################################
#
# Main
#
#####################################

#
# createArchive including OUTPUTDIR, startLog, getConfigEnv
# sets "JOBKEY"
preload ${OUTPUTDIR}

#
#
# create input file
#
echo 'Running omim_hpoload.py'  | tee -a ${LOG_DIAG}
${PYTHON} ${OMIMHPOLOAD}/bin/omim_hpoload.py >> ${LOG_DIAG}
STAT=$?
checkStatus ${STAT} "${OMIMHPOLOAD}/bin/omim_hpoload.py"

#
# run annotation load
#

ANNOTLOAD_CONFIG=${OMIMHPOLOAD}/annotload.config
echo "Running OMIM/HPO annotation load" >> ${LOG_DIAG}
cd ${OUTPUTDIR}
${ANNOTLOADER} ${ANNOTLOAD_CONFIG} omimhpo >> ${LOG_DIAG} 
STAT=$?
checkStatus ${STAT} "${ANNOTLOADER} ${ANNOTLOAD_CONFIG} omimhpo"

#
# run postload cleanup and email logs
#
shutDown

