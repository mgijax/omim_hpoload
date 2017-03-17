#!/usr/local/bin/python

'''
#
# omim_hpoload.py
#
#	See http://mgiwiki/mediawiki/index.php/sw:Omim_hpoload
#
# 	The OMIM/HPO file contains:
#
# 		field 1: Database ID ('OMIM')
# 		field 2: OMIM ID
# 		field 3: OMIM Name
# 		field 4: Qualifier
# 		field 5: HPO ID
# 		field 6: References
# 		field 7: Evidence code
# 		field 8: Onset Modifier
# 		field 9: Frequency Modifier
#		field 10: With
#               field 11: Aspect
#               field 12: Synonym
#               field 13: Date
#               field 14: Assigned By
#
# 	The annotation loader format has the following columns:
#
#	A tab-delimited file in the format:
#		field 1: Accession ID of Vocabulary Term being Annotated to
#		field 2: ID of MGI Object being Annotated (e.g. HPO ID)
#		field 3: J:229231
#		field 4: Evidence Code  (from OMIM/HPO input file)
#		field 5: Inferred From (blank)
#		field 6: Qualifier (from OMIM/HPO input file)
#		field 7: Editor
#		field 8: Date (from OMIM/HPO input file)
#		field 9: Notes (blank)
#		field 10: Disease Ontology
#
#
# Usage:
#       omim_hpoload.py
#
# History:
#
# lec	03/02/2017
#	- TR12540/Disease Ontology
#	input file contains OMIM ids, output/annotation files needs to use 'Disease Ontology'
#
# sc   03/16/2016
#       - created TR12267
#
'''

import sys
import os
import string
import db

# OMIM/HPO file and descriptor
inFileName = os.environ['INFILE_NAME']
fpInFile = None

# annotation load file and descriptor
annotFileName = os.environ['ANNOTFILE_NAME']
fpAnnotFile = None

# QC file and descriptor
qcFileName = os.environ['QCFILE_NAME']
fpQcFile = None
# reference for the load
jnumID = os.environ['JNUM']

# annotation editor value
editor = os.environ['EDITOR']

# list of OMIM/HPO evidence codes from the database
evidenceList = []

# list of OMIM/HPO annotation qualifiers from the database
qualifierList = []

# omim ID: obsolete or active
omimDict = {}

# HPO ids in the database.Note: we do not load obsolete HPO terms
hpoList = []

# Evidence inferred from is null
inferredFrom = ''

# Notes are null
notes = ''

# lines where evidence codes not in the database
evidErrorList = []

# lines where qualifiers not in the database
qualErrorList = []

# lines with invalid HPO IDs
invalidHPOList = []

# lines with invalid OMIM IDs
invalidOMIMList = []

# lines with OMIM IDs that do not map to DO
invalidDOList = []

# lines with obsolete OMIM IDs
obsoleteOMIMList = []

# lookup omim id -> do id
omimToDOLookup = {}

#
# Purpose:  Open and copy files. Create lookups
# Returns: 1 if file does not exist or is not readable, else 0
# Assumes: Nothing
# Effects: Copies & opens files, read a database
# Throws: Nothing
#
def initialize():
    global fpInFile, fpAnnotFile, fpQcFile, evidenceList, qualifierList
    global omimDict, hpoList, omimToDOLookup

    # create file descriptors
    try:
	fpInFile = open(inFileName, 'r')
    except:
	print '%s does not exist' % inFileName
    try:
	fpAnnotFile = open(annotFileName, 'w')
    except:
	print '%s does not exist' % annotFileName
    try:
	fpQcFile = open(qcFileName, 'w')
    except:
	 print '%s does not exist' % qcFileName

    db.useOneConnection(1)

    # load evidence code lookup
    results = db.sql('''select abbreviation
		from VOC_Term
		where _Vocab_key = 107''', 'auto')
    for r in results:
	evidenceList.append(r['abbreviation'])

    # load annotation qualifier lookup
    results = db.sql('''select term
                from VOC_Term
                where _Vocab_key = 108''', 'auto')
    for r in results:
        qualifierList.append(r['term'].lower())

    # load lookup of OMIM IDs in the database
    results = db.sql('''select a.accid, t.isObsolete 
            from ACC_Accession a, VOC_Term t
            where a._LogicalDB_key = 15
            and a._MGIType_key = 13
	    and a.preferred = 1
	    and a._Object_key = t._Term_key''', 'auto')
    for r in results:
	accid = r['accid']
	omimDict[r['accid']] =  r['isObsolete']

    # load lookup of HPO IDs in the database
    results = db.sql('''select a.accid
            from ACC_Accession a, VOC_Term t
            where a._LogicalDB_key = 180
            and a._MGIType_key = 13
            and a.preferred = 1
            and a._Object_key = t._Term_key''', 'auto')
    for r in results:
	hpoList.append(r['accid'])
    db.useOneConnection(0)

    #   
    # omimToDOLookup
    # omim id -> do id
    # only translate OMIM->DO where OMIM translates to at most one DO id
    #   
    results = db.sql('''
	WITH includeOMIM AS (
	select a2.accID
	from ACC_Accession a1, ACC_Accession a2
	where a1._MGIType_key = 13
	and a1._LogicalDB_key = 191
	and a1._Object_key = a2._Object_key
	and a1.preferred = 1
	and a2._LogicalDB_key = 15
	group by a2.accID having count(*) = 1
	)
	select distinct a1.accID as doID, a2.accID as omimID
	from includeOMIM d, ACC_Accession a1, VOC_Term t, ACC_Accession a2
	where d.accID = a2.accID
	and t._Vocab_key = 125
	and t._Term_key = a1._Object_key
	and a1._LogicalDB_key = 191
	and a1._Object_key = a2._Object_key
	and a2._LogicalDB_key = 15
       	''', 'auto')
    for r in results:
        key = r['omimID']
        value = r['doID']
        omimToDOLookup[key] = []
        omimToDOLookup[key].append(value)

#
# Purpose: Read input file and generate Annotation file
# Returns: 1 if file can be read/processed correctly, else 0
# Assumes: Nothing
# Effects: Creates files in the file system
# Throws: Nothing
#
def process():
    global evidErrorList, qualErrorList, fpQcFile
    global invalidOMIMList, invalidDOList, invalidHPOList, obsoleteOMIM

    # build a dictionary of lines to write to output file (annotload input file)
    annotToWriteDict = {}

    # annotation line sans properties - NOTES ARE NULL
    annotLine = '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n'

    lineNum = 0
    for line in fpInFile.readlines():
    	lineNum += 1

	# field 1: Database ID ('OMIM')
	# field 2: OMIM ID
	# field 3: OMIM Name
	# field 4: Qualifier
	# field 5: HPO ID
	# field 6: References
	# field 7: Evidence code
	# field 8: Onset Modifier
	# field 9: Frequency Modifier
	# field 10: With
	# field 11: Aspect
	# field 12: Synonym
	# field 13: Date

	hasError = 0
	tokens = string.split(line[:-1], '\t')
	databaseID = tokens[0]

	if databaseID != 'OMIM':
	    continue

	# attached prefix because this format used in the MGI OMIM vocabulary
	omimID = 'OMIM:' + tokens[1]
	omimName = tokens[2]

	#
	# TR12540/Disease Ontology (DO)
	# translate OMIM id to DO id
	#

        qualifier = tokens[3].lower()
	if qualifier == '':
	    qualifier = 'Not Specified'

	hpoID = tokens[4]
	references = tokens[5]
	evidenceCode = tokens[6]
	onsetModifier =  tokens[7]
	freqModifer = tokens[8]
	withValue = tokens[9]
	aspect = tokens[10]
	synonym = tokens[11] 
	date = tokens[12]

	if evidenceCode not in evidenceList:
	    evidErrorList.append(line)
	    hasError = 1

	if qualifier.lower() not in qualifierList:
	    qualErrorList.append(line)
	    hasError = 1

	# check to see if in database
	if hpoID not in hpoList:
	    invalidHPOList.append(line)
	    hasError = 1

	# check to see if in database
	if omimID not in omimDict.keys():
	   invalidOMIMList.append(line)
	   hasError = 1
	else:
	    # check to see if obsolete
	    if omimDict[omimID] == 1:
		obsoleteOMIMList.append(line)
		hasError = 1

	# check to see if OMIM id maps to DO
	if omimID not in omimToDOLookup:
	   invalidDOList.append(line)
	   hasError = 1
	else:
	    doID = omimToDOLookup[omimID][0]

	if hasError:
	    continue

	#
	# change ddatabaseID from 'OMIM' to 'Disease Ontology'
	# see select * from ACC_LogicalDB where _LogicalDB_key = 191
	#
	databaseID = 'Disease Ontology'
	aLine = annotLine % (hpoID, doID, jnumID, evidenceCode, inferredFrom, qualifier, editor, date, notes, databaseID)
	annotToWriteDict[aLine] = ''
	    
    #
    for line in annotToWriteDict.keys():
        #get the list of properties
        #pList = annotToWriteDict[line]
        #line = line  + string.join(pList, '&===&') + '\n'
        fpAnnotFile.write(line)

    fpQcFile.write('Lines with invalid Evidence Codes\n')
    fpQcFile.write('--------------------------------------------------\n')
    fpQcFile.write(string.join(evidErrorList))
    fpQcFile.write('\nTotal: %s\n' % len(evidErrorList))

    fpQcFile.write('\nLines with invalid Qualifiers\n')
    fpQcFile.write('--------------------------------------------------\n')
    fpQcFile.write(string.join(qualErrorList))
    fpQcFile.write('\nTotal: %s\n' % len(qualErrorList))

    fpQcFile.write('\nLines with invalid OMIM IDs \n')
    fpQcFile.write('--------------------------------------------------\n')
    fpQcFile.write(string.join(invalidOMIMList))
    fpQcFile.write('\nTotal: %s\n' % len(invalidOMIMList))

    fpQcFile.write('\nLines with OMIM IDs that do not map to DO\n')
    fpQcFile.write('--------------------------------------------------\n')
    fpQcFile.write(string.join(invalidDOList))
    fpQcFile.write('\nTotal: %s\n' % len(invalidDOList))

    fpQcFile.write('\nLines with obsolete OMIM IDs\n')
    fpQcFile.write('--------------------------------------------------\n')
    fpQcFile.write(string.join(obsoleteOMIMList))
    fpQcFile.write('\nTotal: %s\n' % len(obsoleteOMIMList))

    fpQcFile.write('\nLines with invalid HPO IDs\n')
    fpQcFile.write('--------------------------------------------------\n')
    fpQcFile.write(string.join(invalidHPOList))
    fpQcFile.write('\nTotal: %s\n' % len(invalidHPOList))

#
# Purpose: Initialization
# Returns: 1 if file does not exist or is not readable, else 0
# Assumes: Nothing
# Effects: Closes files
# Throws: Nothing
#
def closeFiles():

    fpInFile.close()
    fpAnnotFile.close()
    fpQcFile.close()

#
# main
#

initialize()
process()
closeFiles()

