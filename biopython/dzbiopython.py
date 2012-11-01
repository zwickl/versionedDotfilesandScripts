#!/usr/bin/env python
import sys
from os.path import expandvars
import copy
from Bio.SeqFeature import FeatureLocation
from Bio import SeqIO
from BCBio import GFF
from dzutils import read_from_file_or_pickle

#my extensions and functions for working with biopython objects

class TaxonGenomicInformation:
    '''Stores correspondence between a set of sequences, a gff file referring to those 
    sequences and a corresponding toplevel assembly.  Some of these may be omitted.
    Important members:
    name            - taxon name passed to __init__
    self.short_name - first 7 characters of taxon name passed to __init__
    toplevel_record_dict   - dictionary of toplevel SeqRecord.id to toplevel SeqRecords
                        empty if toplevel_filename not passed to __init__
    toplevel_record_list   - list of toplevel SeqRecords in toplevel_record_dict
                        empty if toplevel_filename not passed to __init__
    
    seq_dict        - dictionary of individual SeqRecords (presumably genes or mRNA)
                        existing dict can be passed to __init__, or generated/added to
                        with a passed seq_filename
                        empty if seq_dict or seq_filename not passed to __init__

    if a gff_filename is passed to __init__, several things happen:
        -gff_seqrecord_list is a list filled with SeqRecords for each feature referenced in the gff
        -gff_feature_dict is a dict of either feature Aliases (preferably) or id to SeqFeatures
            that are held by the SeqRecords in gff_seqrecord_list
        -toplevel_record_list is updated to have gff features added to the SeqRecords
        -seq_dict is updated with features from gff
    '''
    
    def __init__(self, name, seq_dict=None, seq_filename=None, toplevel_filename=None, gff_filename=None, usePickle=False):
        '''
        print '#############'
        print name
        print seq_dict
        print seq_filename
        print toplevel_filename
        print gff_filename
        print '#############'
        '''
        self.name = name
        self.short_name = name[0:7]
        
        if toplevel_filename is not None:
            toplevel_filename = expandvars(toplevel_filename)
            if not usePickle:
                #it can be handy to have a dict of the toplevel seq(s) recs which may just be a single chrom
                self.toplevel_record_dict = SeqIO.to_dict(SeqIO.parse(open(toplevel_filename), "fasta"))
                #pull the toplevel reqs back out as a list of seq recs
                self.toplevel_record_list = [it[1] for it in self.toplevel_record_dict.iteritems()]
            else:
                #this is slightly faster reading the pickle than re-parsing
                self.toplevel_record_list = read_from_file_or_pickle(toplevel_filename, toplevel_filename + '.list.pickle', SeqIO.parse, "fasta")
                if not isinstance(self.toplevel_record_list, list):
                    #it may be an iterator or generator rather than list
                    self.toplevel_record_list = [ it for it in self.toplevel_record_list ]
                self.toplevel_record_dict = SeqIO.to_dict(self.toplevel_record_list)

            '''
            print '1#####################'
            for top in self.toplevel_record_list:
                if top.features:
                    print len(self.toplevel_record_list)
                    print type(self.toplevel_record_list)
                    print top
                    print len(top.features)
                    print top.features
                    break
            print '/1#####################'
            '''
        else:
            self.toplevel_record_dict = dict()
            self.toplevel_record_list = []
        
        #if filenames are passed in, do the necessary reading and add them to any dicts/lists that might have been passed
        if seq_dict is None:
            seq_dict = dict()
        if seq_filename is not None:
            seq_filename = expandvars(seq_filename)
            if not usePickle:
                self.seq_dict = SeqIO.to_dict(SeqIO.parse(open(seq_filename), "fasta"))
            else:
                #haven't actually tested pickle here
                self.seq_dict = SeqIO.to_dict(read_from_file_or_pickle(seq_filename, SeqIO.parse, "fasta"))
        else:
            self.seq_dict = dict()
        self.seq_dict.update(seq_dict)

        if gff_filename is not None:
            #pickling the gffs doesn't seem to help - pickle file is much larger than actual gff and slower to read
            gff_filename = expandvars(gff_filename)
            #this will asign features in the gff to the toplevel seqs - the toplevel_record_dict will be unaltered
            #print len(self.toplevel_record_dict.items())
            #I think that we can avoid reading this if we don't have toplevels, but it might bork some script
            if self.toplevel_record_dict:
                self.toplevel_record_list = [feat for feat in GFF.parse(gff_filename, base_dict=self.toplevel_record_dict)]
                #now assign back to the dict
                self.toplevel_record_dict = dict([ (top.id, top) for top in self.toplevel_record_list ])
            '''
            print '2#####################'
            for top in self.toplevel_record_list:
                if top.features:
                    print len(self.toplevel_record_list)
                    print type(self.toplevel_record_list)
                    print top
                    print len(top.features)
                    print top.features
                    break
            print '/2#####################'
            '''
            #print type(self.toplevel)
            #print len(self.toplevel)
            #print "SELF.TOPLEVEL"
            #print self.toplevel[0]
            #print "/SELF.TOPLEVEL"
            self.gff_seqrecord_list = [rec for rec in GFF.parse(gff_filename)]
            '''
            print '3#####################'
            print len(self.gff_seqrecord_list)
            for rec in self.gff_seqrecord_list:
                if rec.features:
                    print rec
                    print len(rec.features)
                    print rec.features
                    break
            if len(self.gff_seqrecord_list) > 1:
                print self.gff_seqrecord_list[1]
            print '/3#####################'
            '''
            self.seq_dict = SeqIO.to_dict([feat for feat in GFF.parse(gff_filename, base_dict=self.seq_dict)])

        else:
            self.gff_seqrecord_list = []
            self.seq_dict = dict()

        if toplevel_filename is not None and gff_filename is not None:
            self.feature_to_toplevel_record_dict = dict()
            for top in self.toplevel_record_list:
                for feat in top.features:
                    if 'Alias' in feat.qualifiers:
                        self.feature_to_toplevel_record_dict[feat.qualifiers['Alias'][0]] = top
                    else:
                        self.feature_to_toplevel_record_dict[feat.id] = top

        self.gff_feature_dict = {}
        if self.gff_seqrecord_list:
            for rec in self.gff_seqrecord_list:
                if rec.features[0].type.lower() in ['chromosome', 'contig', 'scaffold']:
                    #trying to verify when this is happening
                    exit('DEBUG: FIRST RECORD IS %s' % rec.features[0].type)
                    toIter = rec.features[1:]
                else:
                    toIter = rec.features
                for g in toIter:
                    if 'Alias' in g.qualifiers:
                        self.gff_feature_dict[g.qualifiers['Alias'][0]] = g
                    else:
                        self.gff_feature_dict[g.id] = g


    def output(self):
        print '%s\t%d features\t%d dictFeatures\t%d sequences\t%d toplevel records' % (self.name, 
            len(self.gff_seqrecord_list), len(self.gff_feature_dict.keys()), len(self.seq_dict.keys()), len(self.toplevel_record_list))

    def toplevel_record_for_feature(self, feat):
        if isinstance(feat, str):
            if feat in self.feature_to_toplevel_record_dict:
                return self.feature_to_toplevel_record_dict[feat]
            else:
                raise ValueError('toplevel for feature named %s not found!' % feat)
        else:
            if 'Alias' in feat.qualifiers:
                alias = feat.qualifiers['Alias'][0]
                if alias in self.feature_to_toplevel_record_dict:
                    return self.feature_to_toplevel_record_dict[alias]
                else:
                    raise ValueError('toplevel for feature named %s not found!' % alias)
            else:
                fid = feat.id
                if fid in self.feature_to_toplevel_record_dict:
                    return self.feature_to_toplevel_record_dict[fid]
                else:
                    raise ValueError('toplevel for feature named %s not found!' % fid)


def get_taxon_genomic_information_dict(source, report=True, readToplevels=True, usePickle=False):
    #file with lines containing short taxon identifiers, sequence files and gff files for 
    #each taxon
    #like this (on one line)
    #ObartAA	blah	/Users/zwickl/Desktop/GarliDEV/experiments/productionOryza2/gramene34_split/gffs/bartAA.fullWithFixes.gff \
        #/Users/zwickl/Desktop/GarliDEV/experiments/productionOryza2/gramene34_split/toplevels/Oryza_barthii-toplevel-20110818.fa
    if isinstance(source, list):
        if len(source[0]) == 1:
            masterFilenames = [ s.strip.split() for s in source ]
        else:
            masterFilenames = source
    else:
        masterFilenames = [ line.strip().split() for line in open(source, 'rb') if len(line.strip()) > 0 ]

    allTaxonInfo = {}
    for taxon in masterFilenames:
        #ended up not using sequence files, just getting everything from toplevels
        if not readToplevels:
            allTaxonInfo[ taxon[0] ] = TaxonGenomicInformation(taxon[0], gff_filename=taxon[2], usePickle=usePickle)
        else:
            allTaxonInfo[ taxon[0] ] = TaxonGenomicInformation(taxon[0], gff_filename=taxon[2], toplevel_filename=taxon[3], usePickle=usePickle)
        if report:
            allTaxonInfo[ taxon[0] ].output()
    return allTaxonInfo


def parse_feature_name(feature, errorIsFatal=True):
    '''Return what I'm treating as the name of the SeqFeature, which is 
    stored as one of the arbitrarily named qualifiers, named differently
    for IRGSP and OGE gff's
    '''
    #print feature.qualifiers
    if 'Alias' in feature.qualifiers:
        return feature.qualifiers['Alias'][0]
    elif 'Name' in feature.qualifiers:
        return feature.qualifiers['Name'][0]
    else:
        print feature
        if errorIsFatal:
            raise Exception('unable to parse a feature name!:')
        else:
            sys.stderr.write('unable to parse a name!')


def int_feature_location(feat):
    '''Deals with the annoying fact that hoops must be jumped through to make FeatureLocations into numbers
    NOTE: returns location coords in standard biopython format, with start counting from zero, and
    end being one PAST the last base
    edit: D'oh!  Casting isn't necessary'''
    #start = int(str(feat.location.start))
    #end = int(str(feat.location.end))
    #return (start, end)
    return (feat.location.start.position, feat.location.end.position)


def find_cds_start_coordinate(feature):
    '''this will find the "start" of the cds of a gene, which will be the rightmost
    base of a - strand gene, and the first of a + strand gene.  Either way the 
    first CDS listed is the first in the gene, I think.  It needs to deal with the
    fact that the CDS features may be a variable number of layers down from the feature
    passed in.
    NOTE: what the coords mean is VERY misleading.  For a plus strand start is the index
    of the start, and end is one past the index of the last base
    For minus, start is one to the right of the beginning base (reading left to right),
    and end is the index of the leftmost base.
    So, extacting [start:end] will work properly for plus strand,
    and [end:start] will work properly for minus'''

    strandIndex = 0 if feature.strand == 1 else 1
    if feature.type.lower() == 'cds':
        return int_feature_location(feature)[strandIndex]
    for sub in feature.sub_features:
        if sub.type.lower() == 'cds':
            return int_feature_location(sub)[strandIndex]
        for subsub in sub.sub_features:
            if subsub.type.lower() == 'cds':
                return int_feature_location(subsub)[strandIndex]
            for subsubsub in subsub.sub_features:
                if subsubsub.type.lower() == 'cds':
                    return int_feature_location(subsubsub)[strandIndex]


def find_cds_end_coordinate(feature):
    '''see find_cds_start_coordinate notes'''
    #print 'finding cds end'
    #print feature.type, feature.location
    strandIndex = 1 if feature.strand == 1 else 0
    if feature.type.lower() == 'cds':
        return int_feature_location(feature)[strandIndex]
    for sub in reversed(feature.sub_features):
        if sub.type.lower() == 'cds':
            return int_feature_location(sub)[strandIndex]
        for subsub in reversed(sub.sub_features):
            if subsub.type.lower() == 'cds':
                return int_feature_location(subsub)[strandIndex]
            for subsubsub in reversed(subsub.sub_features):
                if subsubsub.type.lower() == 'cds':
                    return int_feature_location(subsubsub)[strandIndex]

def extract_seqrecord_between_outer_cds(rec, ifeat):
    '''This will grab everything between the first and
    last cds of a gene, mainly as a way to chop off any
    UTRs.  This does NOT preperly set the features of the
    returned SeqRecord.
    '''
    if ifeat.sub_features[0].type.lower() == 'mrna':
        if len(ifeat.sub_features) > 1 and ifeat.sub_features[1].type.lower() == 'mrna':
            raise ValueError('Multiple mRNA features found! Pass only one.')
        feat = copy.deepcopy(ifeat.sub_features[0])
    else:
        feat = copy.deepcopy(ifeat)
    
    if feat.strand == -1:
        feat.sub_features.sort(key=lambda x:x.location.start, reverse=True)
    else:
        feat.sub_features.sort(key=lambda x:x.location.start)
    
    '''
    print 'ORIGINAL FEAT'
    print feat
    print feat.location
    print '/ORIGINAL FEAT'
    '''
    s, e = find_cds_start_coordinate(feat), find_cds_end_coordinate(feat)
    print 'start, end', s, e
    tempFeat = copy.deepcopy(feat)
    tempFeat.sub_features = []
    #print
    #print tempFeat.extract(rec)
    #sorting of the cds is necessary for the extraction to work right
    
    tempFeat.location = FeatureLocation(s, e) if feat.strand == 1 else FeatureLocation(e, s)
    
    '''
    print 'TEMP FEAT'
    print tempFeat
    print tempFeat.location
    print '/TEMP FEAT'
    '''
    extracted = tempFeat.extract(rec)
    extracted.name, extracted.id = parse_feature_name(feat), parse_feature_name(feat)

    #DEBUG
    tempFeat.sub_features = collect_features_within_boundaries(feat, min([s, e]), max([s, e]))
    extracted.features = [tempFeat]

    return extracted


def collect_features_within_boundaries(feature, start, end, relativeIndeces=False):
    '''This will pull out the outermost cds fully or partially included in the range,
    and all other intervening features
    this doesn't care about strand, and start should always be < end
    NOTE:the start and end indeces are zero offset
    '''

    #I think that len(feature) actually does a sum of the lengths of all of the subfeatures
    #so, if both exons and cds are included it is longer than the actual length
    realFeatureLength = int_feature_location(feature)[1] - int_feature_location(feature)[0]
    
    '''
    print 'num subfeat', len(feature.sub_features)
    print 'feature loc:', feature.location
    #print 'my feature loc', int_feature_location(feature)
    print 'strand', feature.strand
    print 'feature length:', realFeatureLength
    print 'boundaries:', start, end
    '''

    if start > end:
        #be forgiving here, allowing for reversed coordinates
        if feature.strand == -1:
            print 'flipping start and end coords in collect_features_within_boundaries'
            start, end = end, start
        else:
            raise ValueError('start > end in collect_features_within_boundaries?')

    if relativeIndeces:
        if feature.strand == -1:
            #alignment was of the sequences in sense direction, which didn't know about
            #strand, so need to flip
            start, end = realFeatureLength - end, realFeatureLength - start
        start += int_feature_location(feature)[0]
        end += int_feature_location(feature)[0]
        print 'adjusted boundaries:', start, end

    if feature.type.lower() == 'cds':
        raise ValueError('pass a feature above CDS to find_nearest_cds_boundaries')

    if feature.sub_features[0].type.lower() == 'mrna':
        feature = feature.sub_features[0]

    collectedSubfeatures = []
    #print start, end
    cdsStart = sys.maxint
    cdsEnd = -1
    for sub in feature.sub_features:
        if sub.type.lower() == 'cds':
            fstart, fend = int_feature_location(sub)
            if fend > start and fstart < cdsStart:
                cdsStart = fstart
            if fstart < end and fend > cdsEnd:
                cdsEnd = fend
    #this should grab exons that correspond the cds as well as everything else in between
    for sub in feature.sub_features:
        fstart, fend = int_feature_location(sub)
        if fstart >= cdsStart and fend <= cdsEnd:
            collectedSubfeatures.append(sub)
    if len(collectedSubfeatures) == 0:
        #exit('no features collected?')
        print 'NO CDS FEATURES WITHIN BOUNDARIES: %d, %d!' % (start, end)
    return collectedSubfeatures


def get_first_cds(feature):
    '''this will find the "start" of the cds of a gene, which will be the rightmost
    base of a - strand gene, and the first of a + strand gene.  Either way the 
    first CDS listed is the first in the gene, I think.  It needs to deal with the
    fact that the CDS features may be a variable number of layers down from the feature
    passed in.'''
    if feature.type.lower() == 'cds':
        return feature
    for sub in feature.sub_features:
        if sub.type.lower() == 'cds':
            return sub
        for subsub in sub.sub_features:
            if subsub.type.lower() == 'cds':
                return subsub
            for subsubsub in subsub.sub_features:
                if subsubsub.type.lower() == 'cds':
                    return subsubsub
    print feature
    raise ValueError('no cds found!')


def sort_feature_list_by_id(recList):
    recList.sort(key=lambda rec:rec.features[0].qualifiers['ID'])


def MakeGeneOrderMap(geneOrderFilename):
    '''read the indicated file, which should be a simple file with columns indicating gene number and gene name'''
    mapFile = open(geneOrderFilename, 'rb')
    splitMap = [ line.strip().split() for line in mapFile ]
    mapDict = dict([ (line[1], int(line[0])) for line in splitMap ])
    '''
    mapDict = {}
    for line in splitMap:
        mapDict[line[1]] = int(line[0])
    '''
    return mapDict


def adjust_feature_coords(features, delta):
    '''Shift all feature and subfeature coords by delta'''
    for feature in features:
        start, end = feature.location.start.position + delta, feature.location.end.position + delta
        feature.location = FeatureLocation(start, end)
        adjust_feature_coords(feature.sub_features, delta)


def remove_features(features, namesToRemove):
    '''Remove any features with the specified types'''
    featsToDelete = []
    for feature in features:
        for rem in namesToRemove:
            if feature.type.lower() == rem.lower():
                featsToDelete.append(feature)
    for f in featsToDelete:
        features.remove(f)
    #now remove sub_features from anything not alreay removed
    for feature in features:
        remove_features(feature.sub_features, namesToRemove)


def get_features_by_name(feature, name):
    name = name.lower()
    if feature.type.lower() == name:
        return [feature]
    featsToReturn = []
    for sub in feature.sub_features:
        if sub.type.lower() == name:
            featsToReturn.append(sub)
        for subsub in sub.sub_features:
            if subsub.type.lower() == name:
                featsToReturn.append(subsub)
            for subsubsub in subsub.sub_features:
                if subsubsub.type.lower() == name:
                    featsToReturn.append(subsubsub)
    return featsToReturn


def remove_stop_codon_from_feature(feature):
    '''this just chops off the last three bases of the gene, adjusting gene, mRNA, CDS and exon locations
    it is a simpler version of adjust_for_out_of_phase_cds'''
    assert feature.type == 'gene'

    start, end = int_feature_location(feature)
    adjust = (end, end - 3) if feature.strand == 1 else (start, start + 3)
    #easiest thing to do here will just be to find all mention of a given coordinate and adjust it,
    #which will work for cds, exon, mRNA, gene, etc.
    toSearch = [ feature ]
    for sub in feature.sub_features:
        toSearch.append(sub)
        for subsub in sub.sub_features:
            toSearch.append(subsub)
            for subsubsub in subsub.sub_features:
                toSearch.append(subsubsub)

    for s in toSearch:
        start, end = int_feature_location(s)
        if start == adjust[0]:
            s.location = FeatureLocation(adjust[1], end)
        if end == adjust[0]:
            s.location = FeatureLocation(start, adjust[1])


def append_string_to_feature_names(feature, appStr):
    '''add _appStr to the contents of the following qualifiers, if they exist'''
    for field in ['ID', 'Alias', 'Name', 'Parent']:
        if field in feature.qualifiers:
            feature.qualifiers[field][0] += '_%s' % str(appStr)

    for sub in feature.sub_features:
        append_string_to_feature_names(sub, appStr)


def substitute_feature_names(feature, oldName, newName):
    #print "#######"
    #print feature
    #print oldName
    #print newName
    #print "#######"
    '''replace any appearances of oldName with newName, in id's, qualifiers, etc'''
    if feature.id is not None:
        feature.id = re.sub(oldName, newName, feature.id)
    for field in ['ID', 'Alias', 'Name', 'Parent']:
        if field in feature.qualifiers:
            feature.qualifiers[field][0] = re.sub(oldName, newName, feature.qualifiers[field][0])

    for sub in feature.sub_features:
        substitute_feature_names(sub, oldName, newName)

    if 'Parent' in feature.qualifiers and len(feature.qualifiers['Parent']) > 1:
        exit('MULTIPLE PARENTS?')


