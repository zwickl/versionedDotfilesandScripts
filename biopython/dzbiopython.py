#!/usr/bin/env python
import sys
import os
import copy
from Bio.Seq import Seq
from Bio.SeqFeature import SeqFeature
from Bio.SeqFeature import FeatureLocation
from Bio.SeqRecord import SeqRecord
from Bio import SeqIO
from BCBio import GFF

#my extensions and functions for working with biopython objects

class TaxonGenomicInformation:
    '''Stores correspondence between a set of sequences, a gff file referring to those 
    sequences and a corresponding toplevel assembly.  Some of these may be omitted.'''
    def __init__(self, name, seq_dict=None, seq_filename=None, toplevel_filename=None, gff_filename=None):
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
            #it can be handy to have a dict of the toplevel seq(s) recs which may just be a single chrom
            toplevel_filename = os.path.expandvars(toplevel_filename)
            self.toplevel_dict = SeqIO.to_dict(SeqIO.parse(open(toplevel_filename), "fasta"))
            #pull the toplevel reqs back out as a list of seq recs
            self.toplevel = [it[1] for it in self.toplevel_dict.items()]
            #print 'toplevel name', self.toplevel.name
            #print 'toplevel features', len(self.toplevel.features)
        else:
            self.toplevel_dict = dict()
            self.toplevel = [SeqRecord()]
        
        #if filenames are passed in, do the necessary reading and add them to any dicts/lists that might have been passed
        if seq_dict is None:
            seq_dict = dict()
        if seq_filename is not None:
            seq_filename = os.path.expandvars(seq_filename)
            new_seq_dict = SeqIO.to_dict(SeqIO.parse(open(seq_filename), "fasta"))
            seq_dict.update(new_seq_dict)
        self.seq_dict = seq_dict

        if gff_filename is not None:
            gff_filename = os.path.expandvars(gff_filename)
            #this will asign features in the gff to the toplevel seqs - the toplevel_dict will be unaltered
            self.toplevel = [feat for feat in GFF.parse(gff_filename, base_dict=self.toplevel_dict)]
            self.gff = [feat for feat in GFF.parse(gff_filename)]
            self.seq_dict = SeqIO.to_dict([feat for feat in GFF.parse(gff_filename, base_dict=self.seq_dict)])

        else:
            self.gff = []
        #self.gff = gff

        self.gff_feature_dict = {}
        if len(self.gff) > 0:
            for rec in self.gff:
                if rec.features[0].type in ['chromosome', 'contig', 'scaffold']:
                    toIter = rec.features[1:]
                else:
                    toIter = rec.features
                for g in toIter:
                    if 'Alias' in g.qualifiers:
                        self.gff_feature_dict[g.qualifiers['Alias'][0]] = g
                    else:
                        self.gff_feature_dict[g.id] = g

            '''
            if self.gff[0].features[0].type == 'chromosome':
                toIter = self.gff[0].features[1:]
            else:
                toIter = self.gff[0].features
            for g in toIter:
                if 'Alias' in g.qualifiers:
                    self.gff_feature_dict[g.qualifiers['Alias'][0]] = g
                else:
                    self.gff_feature_dict[g.id] = g
    '''

    def output(self):
        print '%s\t%d features\t%d dictFeatures\t%d sequences\t%d toplevel bases' % (self.name, 
            len(self.gff), len(self.gff_feature_dict.keys()), len(self.seq_dict.keys()), len(self.toplevel))


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
        print 'unable to parse a name!:'
        print feature
        if errorIsFatal:
            exit()


def int_feature_location(feat):
    '''Deals with the annoying fact that hoops must be jumped through to make FeatureLocations into numbers
    NOTE: returns location coords in standard biopython format, with start counting from zero, and
    end being one PAST the last base'''
    start = int(str(feat.location.start))
    end = int(str(feat.location.end))
    return (start, end)


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
    if feature.type == 'CDS':
        if feature.strand == 1:
            return int_feature_location(sub)[0]
        else:
            return int_feature_location(sub)[1]
    for sub in feature.sub_features:
        if sub.type == 'CDS':
            if feature.strand == 1:
                #print 'SUB'
                #print sub
                #print "return %d" % int_feature_location(sub)[0]
                return int_feature_location(sub)[0]
            else:
                #print 'SUB'
                #print sub
                #print "return %d" % int_feature_location(sub)[1]
                return int_feature_location(sub)[1]
        for subsub in sub.sub_features:
            if subsub.type == 'CDS':
                if feature.strand == 1:
                    return int_feature_location(subsub)[0]
                else:
                    return int_feature_location(subsub)[1]
            for subsubsub in subsub.sub_features:
                if subsubsub.type == 'CDS':
                    if feature.strand == 1:
                        return int_feature_location(subsubsub)[0]
                    else:
                        return int_feature_location(subsubsub)[1]


def find_cds_end_coordinate(feature):
    '''see find_cds_start_coordinate notes'''
    #print 'finding cds end'
    #print feature.type, feature.location
    if feature.type == 'CDS':
        if feature.strand == 1:
            return int_feature_location(sub)[1]
        else:
            return int_feature_location(sub)[0]
    for sub in reversed(feature.sub_features):
        #print '',sub.type, sub.location
        if sub.type == 'CDS':
            if feature.strand == 1:
                return int_feature_location(sub)[1]
            else:
                return int_feature_location(sub)[0]
        for subsub in reversed(sub.sub_features):
            #print '', '', subsub.type, subsub.location
            if subsub.type == 'CDS':
                if feature.strand == 1:
                    return int_feature_location(subsub)[1]
                else:
                    return int_feature_location(subsub)[0]
            for subsubsub in reversed(subsub.sub_features):
                if subsubsub.type == 'CDS':
                    if feature.strand == 1:
                        return int_feature_location(subsubsub)[1]
                    else:
                        return int_feature_location(subsubsub)[0]

def extract_seqrecord_between_outer_cds(rec, ifeat):
    '''This will grab everything between the first and
    last cds of a gene, mainly as a way to chop off any
    UTRs.  This does NOT preperly set the features of the
    returned SeqRecord.
    '''
    if ifeat.sub_features[0].type == 'mRNA':
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
    s = find_cds_start_coordinate(feat)
    e = find_cds_end_coordinate(feat)
    print 'start, end', s, e
    tempFeat = copy.deepcopy(feat)
    tempFeat.sub_features = []
    #print
    #print tempFeat.extract(rec)
    #sorting of the cds is necessary for the extraction to work right
    if feat.strand == 1:
        tempFeat.location = FeatureLocation(s, e)
    else:
        tempFeat.location = FeatureLocation(e, s)
    '''
    print 'TEMP FEAT'
    print tempFeat
    print tempFeat.location
    print '/TEMP FEAT'
    '''
    extracted = tempFeat.extract(rec)
    extracted.name = parse_feature_name(feat)
    extracted.id = parse_feature_name(feat)

    #DEBUG
    tempFeat.sub_features = collect_features_within_boundaries(feat, min([s,e]), max([s,e]))
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
            temp = start
            start = end
            end = temp
        else:
            print 'start > end in collect_features_within_boundaries?'
            exit()

    if relativeIndeces:
        if feature.strand == -1:
            #alignment was of the sequences in sense direction, which didn't know about
            #strand, so need to flip   
            newstart = realFeatureLength - end
            end = realFeatureLength - start
            start = newstart
        start += int_feature_location(feature)[0]
        end += int_feature_location(feature)[0]
        print 'adjusted boundaries:', start, end

    if feature.type == 'CDS':
        exit('pass a feature above CDS to find_nearest_cds_boundaries')

    if feature.sub_features[0].type == 'mRNA':
        feature = feature.sub_features[0]

    collectedSubfeatures = []
    #print start, end
    cdsStart = sys.maxint
    cdsEnd = -1
    for sub in feature.sub_features:
        if sub.type == 'CDS':
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
    if feature.type == 'CDS':
        return feature
    for sub in feature.sub_features:
        if sub.type == 'CDS':
            return sub
        for subsub in sub.sub_features:
            if subsub.type == 'CDS':
                return subsub
            for subsubsub in subsub.sub_features:
                if subsubsub.type == 'CDS':
                    return subsubsub
    print feature
    exit('no cds found!')


def sort_feature_list_by_id(recList):
    recList.sort(key=lambda rec:rec.features[0].qualifiers['ID'])


def MakeGeneOrderMap(geneOrderFilename):
    '''read the indicated file, which should be a simple file with columns indicating gene number and gene name'''
    mapFile = open(geneOrderFilename)
    splitMap = [ line.split() for line in mapFile ]
    mapDict = {}
    for line in splitMap:
        mapDict[line[1]] = int(line[0])
    return mapDict


def adjust_feature_coords(features, delta):
    '''Shift all feature and subfeature coords by delta'''
    for feature in features:
        start = int(str(feature.location.start)) + delta 
        end = int(str(feature.location.end)) + delta 
        feature.location = FeatureLocation(start, end)
        adjust_feature_coords(feature.sub_features, delta)


def remove_features(features, namesToRemove):
    '''Remove any features with the specified types'''
    featsToDelete = []
    for feature in features:
        for rem in namesToRemove:
            if feature.type == rem:
                featsToDelete.append(feature)
    for f in featsToDelete:
        features.remove(f)
    #now remove sub_features from anything not alreay removed
    for feature in features:
        remove_features(feature.sub_features, namesToRemove)


