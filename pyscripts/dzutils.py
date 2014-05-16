#!/usr/bin/env python
import sys
import re
from os import path, stat
import cPickle
from collections import Iterable
from itertools import izip, combinations
from argparse import ArgumentTypeError, ArgumentParser
import numpy as np


class locus_support_details(object):
    '''The basic details of the results of a particular locus (alignment) tree search for a particular triplet + outgroup of 
    taxa.  i.e., one line from the old table format
    can pass the individual elements that would be extracted from a line like
    ../../..//mafft.cds/analyses/boot.garli/runs//aligned.blink.00025.00013.11T.noDupes.2751C.boot.tre   0.5900  0.0000  0.0450  0.7117  0.1217  0.1667  0   0   0   0   0   0   0   0   (O. sativaj AA,O. punctata BB)
    or just pass the line and have the __init__ parse it
    '''
    def __init__(self, treefile=None, support_value_list=None, taxon_locus_coordinate_list=None, taxon_locus_order_list=None, locus_info=None, support_threshold=0.5):

        if locus_info:
            if isinstance(locus_info, list):
                self.locus_string = '\t'.join(locus_info)
                split_info = locus_info
            else:
                self.locus_string = locus_info.strip()
                #need to split on tabs here because some columns can have spaces within
                split_info = locus_info.strip().split('\t')
            treefile = treefile or split_info[0]
            support_value_list = support_value_list or split_info[1:4]
            taxon_locus_coordinate_list = taxon_locus_coordinate_list or split_info[7:11]
            taxon_locus_order_list = taxon_locus_order_list or split_info[11:15]

        self.treefile = treefile
        self.support_threshold = support_threshold
        
        self.support_value_list = [ float(val) for val in support_value_list ]
        support_sum = sum( self.support_value_list )
        if support_sum:
            self.rescaled_support_value_list = [ val / support_sum for val in self.support_value_list if support_sum ]
        else:
            self.rescaled_support_value_list = [ 1.0/3.0 for _ in self.support_value_list ]

        self.taxon_locus_coordinate_list = [ int(val) for val in taxon_locus_coordinate_list ]
        self.taxon_locus_order_list = [ int(val) for val in taxon_locus_order_list ]

        for num, val in enumerate(self.support_value_list):
            if val > self.support_threshold:
                self.supported_tree_num = num
                break
        else:
            self.supported_tree_num = -1

    def __repr__(self):
        if self.locus_string:
            return self.locus_string
        return '%s\t%s\t%s\t%s\t%s' % (self.treefile, '\t'.join(self.support_value_list), '\t'.join(self.rescaled_support_value_list), '\t'.join(self.taxon_locus_coordinate_list), '\t'.join(self.taxon_locus_order_list))

    def __hash__(self):
        return hash(self.treefile)

    def __eq__(self, other):
        return other and self.treefile == other.treefile

    def __ne__(self, other):
        return not self.__eq__(other)


class triplet_support_details(list):
    '''A list of the results of many loci (locus_support_details) allowing various summaries and manipulations.
    Derived from type list, so list operations can be done on self.'''

    def __init__(self, locus_list=None):
        self.extend(locus_list or []) 

    def coordinate_sort(self, taxon=0):
        self.sort(key=lambda loc:loc.taxon_locus_coordinate_list[taxon])

    def order_sort(self, taxon=0):
        self.sort(key=lambda loc:loc.taxon_locus_order_list[taxon])

    def tree_num_list(self):
        return [ loc.supported_tree_num for loc in self ]

    def coordinate_list(self, taxon=0):
        return [ loc.taxon_locus_coordinate_list[taxon] for loc in self ]

    def treefile_list(self):
        return [ loc.treefile for loc in self ]

    def locus_distance_list(self, taxon=0):
        dists = []
        coord = self[0].taxon_locus_coordinate_list[taxon] 
        for loc in self[1:]:
            dists.append(loc.taxon_locus_coordinate_list[taxon] - coord)
            coord = loc.taxon_locus_coordinate_list[taxon]
        return dists

    def informative_tree_num_list(self):
        return [ loc.supported_tree_num for loc in self if loc.supported_tree_num != -1 ]

    def extract_informative_loci(self):
        return triplet_support_details( [ loc for loc in self if loc.supported_tree_num != -1 ] )

    def extract_loci_with_function(self, func):
        return triplet_support_details( [ loc for loc in self if func(loc) ] )

    def extract_loci_in_coordinate_window(self, start, end, taxon):
        ret = triplet_support_details( [ loc for loc in self if start <= loc.taxon_locus_coordinate_list[taxon] < end ] )
        ret.coordinate_sort()
        return ret

    def split_into_runs(self, informative_only=True):
        runs = []
        
        if informative_only:
            loci = self.extract_informative_loci()
        else:
            loci = self
        
        match_start = 0
        topology = self[0].supported_tree_num
        for num, locus in enumerate(self[1:], 1):
            if locus.supported_tree_num != topology or num == len(self):
                runs.append(triplet_support_details(self[match_start:num]))
                match_start = num
            topology = locus.supported_tree_num
        
        return runs

    def shuffle(self):
        np.random.shuffle(self)

    def supported_tree_counts(self):
        return [ len([loc for loc in self if loc.supported_tree_num == tnum]) for tnum in [ 0, 1, 2, -1 ] ]

    def supported_tree_proportions(self):
        if self:
            return [ supp / float(len(self)) for supp in self.supported_tree_counts() ]
        else:
            return [ 0.0, 0.0, 0.0 ]

    def windowed_tree_counts(self, window_size, window_stride, taxon=0):
        largest_coordinate = max([locus.taxon_locus_coordinate_list[taxon] for locus in self])
        return [ self.extract_loci_in_coordinate_window(start, start + window_size, taxon).supported_tree_counts() for start in xrange(1, largest_coordinate + 1, window_stride) ]

    def windowed_tree_proportions(self, window_size, window_stride, taxon=0):
        largest_coordinate = max([locus.taxon_locus_coordinate_list[taxon] for locus in self])
        return [ self.extract_loci_in_coordinate_window(start, start + window_size, taxon).supported_tree_proportions() for start in xrange(1, largest_coordinate + 1, window_stride) ]

    def count_adjacent_tree_matches(self):
        return sum( [self[num].supported_tree_num == self[num + 1].supported_tree_num for num in xrange(len(self) - 1)] )

    def match_distance_tuples(self, taxon=0):
        return [ (self[num].supported_tree_num == self[num + 1].supported_tree_num, self[num + 1].taxon_locus_coordinate_list[taxon] - self[num].taxon_locus_coordinate_list[taxon]) for num in xrange(len(self) - 1)] 

    def max_coordinate(self, taxon=0):
        return max(locus.taxon_locus_coordinate_list[taxon] for locus in self)

    def support_mean(self, topology=0, informative_only=True, only_if_topology_preferred=False):
        if informative_only:
            loci = self.extract_informative_loci()
        else:
            loci = self
        if only_if_topology_preferred:
            sublist = [locus.support_value_list[topology] for locus in loci if locus.supported_tree_num == topology]
            return sum(sublist) / float(len(sublist))
        else:
            return sum([locus.support_value_list[topology] for locus in loci]) / float(len(loci))

    def support_sum(self, topology=0, informative_only=True, only_if_topology_preferred=False):
        if informative_only:
            loci = self.extract_informative_loci()
        else:
            loci = self
        if only_if_topology_preferred:
            sublist = [locus.support_value_list[topology] for locus in loci if locus.supported_tree_num == topology]
            return sum(sublist)
        else:
            return sum([locus.support_value_list[topology] for locus in loci])

    def __repr__(self):
        outstr = ''
        for locus in self:
            outstr += '%s\n' % locus
        return outstr
            

def flattened_array_generator(array, level=1, reverse=False):
    '''Generator to be used in flatten_array function, or by itself'''
    if isinstance(array, Iterable) and not isinstance(array, str):
        if reverse:
            array = array[::-1]

        for toplvl in array:
            if level == 0:
                yield toplvl
            else:
                for sub in flattened_array_generator(toplvl, level=level-1, reverse=reverse):
                    yield sub
    else:
        yield array


def flatten_array(array, levels=1, reverse=False):
    '''Return a list with outermost levels of the input list eliminated
    Thus, one level just removes the outermost list, etc.  See doctest
    examples.
    >>> flatten_array([[1, 2, 3], [4, 5, 6]])
    [1, 2, 3, 4, 5, 6]
    >>> flatten_array([[1, [2, 3]], [[4, 5], 6]], levels=2)
    [1, 2, 3, 4, 5, 6]
    >>> flatten_array([[1, [2, 3]], [[4, 5], 6]], levels=2, reverse=True)
    [6, 5, 4, 3, 2, 1]
    >>> flatten_array([[1, [2, 3]], [[4, 5], 6]], levels=1)
    [1, [2, 3], [4, 5], 6]
    >>> flatten_array([[1, [2, 3]], [[4, 5], 6]], levels=1, reverse=True)
    [6, [4, 5], [2, 3], 1]
    '''
    ret = []
    for el in flattened_array_generator(array, level=levels, reverse=reverse):
        ret.append(el)
    return ret


class UniqueSubstringClass(object):
    '''This is used for the function find_shortest_unique_leading_substrings'''
    def __init__(self, full_string):
        self.full_string = full_string
        self.cur_len = 1

    def __eq__(self, other):
        return self.substr() == other.substr()

    def clashes(self, other):
        '''If this can't be advanced further, don't consider it clashing'''
        if self.can_advance() and re.match(self.substr(), other.substr()):
            return True
        return False

    def substr(self):
        return self.full_string[:self.cur_len]

    def advance(self):
        if self.can_advance():
            self.cur_len += 1

    def can_advance(self):
        return self.cur_len < len(self.full_string)


def find_shortest_unique_leading_substrings(string_list):
    '''This just takes the list of strings and finds the shortest substrings
    from their beginnings that make them all unique, if possible. It should
    be order-invariant.
    >>> find_shortest_unique_leading_substrings(['aba', 'a', 'cab', 'ac'])
    ['ab', 'a', 'c', 'ac']
    >>> find_shortest_unique_leading_substrings(['ac', 'a', 'cab', 'aba'])
    ['ac', 'a', 'c', 'ab']
    >>> find_shortest_unique_leading_substrings(['ac', 'a', 'cab', 'ac'])
    ['ac', 'a', 'c', 'ac']
    '''
    substrs = [ UniqueSubstringClass(string) for string in string_list ]

    for first, sec in combinations(substrs, 2):
        while first.clashes(sec) or sec.clashes(first):
            if first.clashes(sec) and first.can_advance():
                first.advance()
            if sec.clashes(first) and sec.can_advance():
                sec.advance()

    return [ string.substr() for string in substrs ]

    '''
    for num1, num2 in itertools.combinations(nums):
        first, sec = tuple_list[num1], tuple_list[num2]
        while re.match(first[1], sec[1]) or re.match(sec[1], first[1]):
            if re.match(first[1], sec[1]):
                first[1] = 
        first[1], sec[1] = 
        while first[1] == sec[1]:
    '''



def proportion_type(string):
    '''This is used for type and bound checking, specified as a type= argument in argparse.add_argument().
    It would be nice to be able to pass as specific range besides 0.0-1.0, but funcs used for type= can 
    only take 1 arg.
    On failure raises an ArgumentTypeError, defined by argparse.
    >>> proportion_type('1.0')
    1.0
    >>> proportion_type('1.1')
    Traceback (most recent call last):
    ...
    ArgumentTypeError: value 1.100000 must be between 0.00 and 1.00
    '''
    min_val, max_val = 0.0, 1.0
    value = float(string)
    if value < min_val or value > max_val:
        mess = 'value %f must be between %.2f and %.2f' % (value, min_val, max_val)
        raise ArgumentTypeError(mess)
    return value


class BarebonesArgumentParser(ArgumentParser):
    def __init__(self, **kwargs):
        #these are the defaults which can be overwridden with keyword arguments
        defaultInput = kwargs.pop('defaultInput', True)
        defaultOutput = kwargs.pop('defaultOutput', sys.stdout)
        
        #base constructor
        super(BarebonesArgumentParser, self).__init__(self, **kwargs)
        
        if defaultInput is not False:
            self.add_argument('-i', '--input', dest='inFiles', nargs='*', type=str, default=None, 
                                help='intput files')

        if defaultOutput is not False:
            self.add_argument('-o', '--output', dest='outFile', type=str, default=defaultOutput, 
                                help='file to write output to (default stdout)')


def read_from_file_or_pickle(filename, pickleName, readFunc, *readFuncArgs, **readFuncKwargs):
    '''This takes a filename, and a function that would be used to parse that file, as well as arguments for
    that parsing function.  If there is a file with the name <filename>.pickle that is more recent than 
    <filename>, it will be unpickled into an object and returned.  Otherwise the parsing function will be 
    called on the file, and the result pickled and returned.

    The unsatisfying thing is that some parsing functions may return a generator rather than a list, dict or
    other object.  Generators are not pickle-able, so this causes a problem.  Currently if the object returned
    from the parse is a generator, cast it as a list before pickling it.  For many cases this will be fine for 
    client code, but it obviously will not be ideal if the caller doesn't want the whole list in memory.
    This is currently the caller's responsibility, and if they want a generator, don't use this function.  
    For many cases this will be fine for client code, but it obviously will not be ideal if the caller 
    doesn't want the whole list in memory.
    NOTE: This is currently the caller's responsibility, and if they want a generator, don't use this function.
    '''
    if path.exists(filename):
        sourceTime = stat(filename).st_mtime
    else:
        raise IOError("file %s doesn't exist?" % filename)
    
    #pickleName = filename + ".pickle"
    pickleOK = False
    if path.exists(pickleName):
        pickleTime = stat(pickleName).st_mtime
        if sourceTime <= pickleTime:
            pickleOK = True
        else:
            sys.stderr.write('pickle file %s is too old, rewriting\n')

    if pickleOK:
        with open(pickleName, 'rb') as pickleIn:
            sys.stderr.write('reading pickle file %s... ' % pickleName)
            parsed = cPickle.load(pickleIn)
            sys.stderr.write('done\n')
    else:
        with open(filename, 'rb') as fileIn:
            parsed = readFunc(filename, *readFuncArgs, **readFuncKwargs)
            import inspect
            if inspect.isgenerator(parsed):
                parsed = list(parsed)
        with open(pickleName, 'wb') as pickleOut:
            sys.stderr.write('writing pickle file %s... ' % pickleName)
            import inspect
            if inspect.isgenerator(parsed):
                parsed = list(parsed)
            cPickle.dump(parsed, pickleOut, cPickle.HIGHEST_PROTOCOL)
            sys.stderr.write('done\n')
    return parsed


def extract_sequences_and_stuff_from_nexus_file(nfile, taxToSequenceDict, beginningLinesInNexus=None, endLinesInNexus=None):
    '''this just gets some random stuff that I extract from a nexus file that I was using in a few different scripts
    this includes a dictionary of taxon names to sequences, the lines in the file before the matrix, and the lines
    in the file after the matrix'''
    foundSequences = False
    finishedSequences = False
    with open(nfile, 'rb') as nexusFile:
        for line in nexusFile:
            #get the sequence lines in the nexus file
            
            if 'matrix' in line.lower() and not foundSequences:
                foundSequences = True
                if beginningLinesInNexus:
                    beginningLinesInNexus.append(line)

            elif foundSequences and not finishedSequences:
                #this is assuming that the matrix ends with a line containing only a semicolon and whitespace
                if re.search('^;', line.strip()):
                    finishedSequences = True
                    if endLinesInNexus:
                        endLinesInNexus.append(line)
                else:
                    stuff = line.split()
                    #taxon name that starts each matrix line can either be quoted or underscored to escape the spaces
                    if re.search('^[\']', line) or re.search('^[OL][.]', line):
                        #want to go from 
                        #'Oryza blah AA' ACGT... to [ 'Oryza blah AA', 'ACGT...' ]
                        #this looks like an ugly way to do this, but is much faster than using shlex as I used to
                        #stuff = shlex.split(line)
                        stuff = [ re.sub('\'', '', ' '.join(stuff[:-1])), stuff[-1] ]

                    if len(stuff) != 2:
                        sys.exit("problem parsing line %s" % line)
                    taxToSequenceDict[stuff[0]] = stuff[1]
            else:
                #if endLinesInNexus and foundSequences:
                if endLinesInNexus is not None and finishedSequences:
                    endLinesInNexus.append(line)
                if beginningLinesInNexus is not None and not foundSequences:
                    beginningLinesInNexus.append(line)
 

class CoordinateSet(object):
    '''A set of chromosomal coordinates for each sequence in an alignment
    Single copy ONLY!  Missing taxa are allowed though
    '''
    def __init__(self, taxa_names):
        self.defaultCoord = -1
        self.seqCoords = {}
        if not taxa_names:
            sys.exit("you must pass a list of taxon names")
        self.seqCoords = dict.fromkeys( taxa_names, self.defaultCoord )
    
    def set_coordinate(self, taxon, coord):
        if taxon in self.seqCoords:
            if self.seqCoords[taxon] is not None:
                self.seqCoords[taxon] = int(coord)
        else:
            print self.seqCoords
            sys.exit("trying to assign coordinate to unknown taxon: %s" % taxon)

    def set_filename(self, name):
        self.filename = name
        self.short_filename = extract_core_filename(name)
    
    def output(self):
        for name, coord in self.seqCoords.iteritems():
            print name, coord

    def __getitem__(self, taxon_label):
        return self.seqCoords[taxon_label]

    def row_output(self, taxon_labels=None):
        mystr = ''
        if taxon_labels is None:
            #this will sort the columns alphabetically by taxon name
            for t in sorted(self.seqCoords.iterkeys()):
                mystr += '%d\t' % int(self.seqCoords[t])
        #IMPORTANT: if taxon labels are passed in, the coord order will be the same, NOT alphabetical
        else:
            try:
                for lab in taxon_labels:
                    mystr += '%d\t' % int(self.seqCoords[lab])
            except:
                sys.exit('could not match taxon %s with any coordinate' % lab)
        return mystr


def extract_core_filename(name, no_nchar=False):
    '''
    extract the "core" portion of a filename, regardless of exactly what the original filename is
    this includes the cluster number, number of taxa, number of characters and other stuff
    6/4/13 - changed this to pull off the ".gblocks" at the end, if present
    >>> extract_core_filename('../alignments/aligned.blink.00047.00002.8T.noDupes.954C.nex')
    '00047.00002.8T.noDupes.954C'
    >>> extract_core_filename('../../alignments/aligned.blink.00000.00000.10T.noDupes.2079C.gblocks.nex')
    '00000.00000.10T.noDupes.2079C'
    >>> extract_core_filename('../garli.gblocks.collapse/runs/aligned.blink.00000.00000.10T.noDupes.2079C.gblocks.best.tre')
    '00000.00000.10T.noDupes.2079C'

    '''
    extracted = None
    patts = [ '^.*blink[.](.*)', '^.*clique[.](.*)', '^.*MCL.*[.](.*)', '^.*MCcoalSim[.](.*)' ]
    for p in patts:
        search = re.search(p, name)
        if search:
            extracted = search.group(1)
            break
    if extracted is None:
        exit("problem shortening name 1: %s" % name)
  
    if 'gblocks' in extracted:
        extracted = re.sub('.gblocks', '', extracted)
    extracted2 = None
    #don't think that these really need to be at the end of lines
    #patts = [ '(.*).nex$', '(.*).best.tre$', '(.*).boot.tre$', '(.*).tre$', '(.*).boot$' ]
    suffixes = [ '.nex', '.best.tre', '.boot.tre', '.tre', '.boot', '.conf', '.sh', '.scores', '.modelfit.log', '.screen.log', '.log00.log', '.sitelikes.log' ]
    #patts = [ '(.*).nex', '(.*).best.tre', '(.*).boot.tre', '(.*).tre', '(.*).boot', '(.*).conf', '(.*).sh' ]

    for suff in suffixes:
        if suff in extracted:
            search = re.search('(.*)' + suff, extracted)
            if search:
                extracted2 = search.group(1)
                break
            else:
                sys.exit('WTF?')
    '''
    for p in patts:
        search = re.search(p, extracted)
        if search:
            extracted2 = search.group(1)
            break
    '''
    if extracted2 is None:
        if extracted[-1] != 'C':
            exit("problem shortening name 2: %s" % name)
        else:
            extracted2 = extracted

    if no_nchar:
        search = re.search('(.*)[.].*C$', extracted2)
        if search:
            extracted2 = search.group(1)

    return extracted2


def parse_numerical_filename_details(name):
    '''
    >>> parse_numerical_filename_details('../alignments/aligned.blink.00047.00002.8T.noDupes.954C.nex')
    (47, 2, 8, 954)
    >>> parse_numerical_filename_details('../../alignments/aligned.blink.00000.00000.10T.noDupes.2079C.gblocks.nex')
    (0, 0, 10, 2079)
    >>> parse_numerical_filename_details('../garli.gblocks.collapse/runs/aligned.blink.00000.00000.10T.noDupes.2079C.gblocks.best.tre')
    (0, 0, 10, 2079)
    '''
    core = extract_core_filename(name)
    search = re.search('([0-9]+)[.]([0-9]+)[.]([0-9]+)T[.][a-zA-Z]+[.]([0-9]+)C.*', core)
    if search:
        return int(search.group(1)), int(search.group(2)), int(search.group(3)), int(search.group(4))
    else:
        exit("count not parse %s" % name)


class DagLine(object):
    '''Simple container for dagchainer formatted lines.'''
    def __init__(self, line):
        '''Store whole line as string, and some parsed fields.
        
        arguments:
        line -- either a string or a string that was pre-split into fields (should be 9 of them)
        
        members:
        string -- normalized to have fields separated by tabs
        cut_string -- same fields, minus the last one, which is a floating point value and can
            be represented differently.  Allows proper hashing and equality detection of lines, 
            minus the evalue.
        self.tax[12] -- taxon names, pulled from fields 1 and 5
        self.evalue -- 'nuf said
        '''
        self.fields = line.split() if isinstance(line, str) else line
        '''
        if isinstance(line, str):
            self.fields = line.split()
        else:
            self.fields = line
        '''
        if len(self.fields) != 9:
            raise ValueError('Wrong number of fields in dag string')
        self.string = '\t'.join(self.fields)
        #this is just the line string minus the e-value, which can be represented in text multiple ways
        self.cut_string = '\t'.join(self.fields[:-1])
        self.tax1, self.tax2, self.evalue = self.fields[1], self.fields[5], self.fields[8]

    def __hash__(self):
        return hash(self.cut_string)
    
    def __cmp__(self, other):
        raise Exception
        sys.stderr.write('CMP %s %s' % (self, other))
        #return cmp(self.cut_string, other.cut_string)
        return cmp((self.tax1, self.tax2), (other.tax1, other.tax2))
    
    def __eq__(self, other):
        return self.cut_string == other.cut_string
    
    def __ne__(self, other):
        return not self.__eq__(other)
    
    def __lt__(self, other):
        if self.tax1 != other.tax1:
            return self.tax1 < other.tax1
        else:
            return self.tax2 < other.tax2
    
    def __str__(self):
        return self.string


def my_dag_sort(first, sec):
    '''Sort by first taxon, then second.'''
    if first[1] != sec[1]:
        if first[1] < sec[1]:
            return True
        return False
    else:
        if first[5] != sec[5]:
            if first[5] < sec[5]:
                return True
            return False
        else:
            return False


def parse_daglines(infile, self_hits=False):
    if isinstance(infile, str):
        hand = open(infile, 'r')
    else:
        hand = infile

    lines = [ line.split() for line in hand if not '#' in line ]
    lines.sort()
    if self_hits:
        dagLines = [ DagLine(line) for line in lines ]
    else:
        dagLines = [ DagLine(line) for line in lines if line[1] != line[5] ]
    return dagLines


class BlinkCluster(object):
    def __init__(self, num, members=None, dagLines=None, daglineDoubleDict=None, mapping=None):
        if members is None:
            members = []
        #print members
        #for iteration
        self.index = 0
        self.number = num
        if mapping is None:
            self.cluster_members = members
        else:
            self.cluster_members = []
            for member in members:
                self.cluster_members.append(mapping[member])
        
        self.cluster_members.sort()
    
        self.member_set = set(tuple(sorted(self.cluster_members))) if self.cluster_members else set()

        taxonDict = {}
        for memb in self.cluster_members:
            if memb[0:7] in taxonDict:
                self.noDupes = False
                break
            else:
                taxonDict[memb[0:7]] = True
        else:
            self.noDupes = True

        if dagLines is not None and len(dagLines):
            #daglineDoubleDict = get_dagline_double_dict(dagLines)
            daglineDoubleDict = get_dagline_double_dict_from_dagline_objects(dagLines)
        else:
            self.dag_lines = []
            self.dag_line_set = set()
        if daglineDoubleDict:
            self.dag_lines = get_dagline_list_for_cluster(self.cluster_members, daglineDoubleDict)
            self.dag_line_set = get_dagline_set_for_cluster(self.cluster_members, daglineDoubleDict)
            if not self.dag_lines and len(self.cluster_members) > 1:
                print len(daglineDoubleDict)
                print self
                exit('no daglines %d?' % len(self.cluster_members))
        else:
            self.dag_lines = []
            self.dag_line_set = set()

        if self.dag_line_set is None:
            print 'no dagline set?'
            print self

    def add(self, member):
        self.cluster_members.append(member)
    
    def __len__(self):
        return len(self.cluster_members)
    
    def output(self, stream=sys.stdout):
        for mem in self.cluster_members:
            stream.write('%d\t%s\n' % (self.number, mem))
    
    def __repr__(self):
        string = 'cluster %d ' % self.number
        string += '%d members\n' % len(self.cluster_members)
        for mem in self.cluster_members:
            string += '\t%d\t%s\n' % (self.number, mem)
        string += 'daglines\n'
        if self.dag_lines:
            for line in self.dag_lines:
                if isinstance(line, DagLine):
                    string += '\t%s\n' % line.string
                else:
                    string += '\t%s\n' % line
        else:
            string += '\tdaglines not defined\n'
        return string

    def __str__(self):
        return ''.join(['\t%d\t%s\n' % (self.number, mem) for mem in self.cluster_members ])

    def contains_matching_taxon(self, patt):
        for m in self.cluster_members:
            if re.search(patt, m) is not None:
                return True
        return False
    
    def __contains__(self, name):
        return name in self.cluster_members
        '''
        if name in self.cluster_members:
            return True
        return False
        '''
    
    def __iter__(self):
        return self
    
    def next(self):
        try:
            result = self.cluster_members[self.index]
        except IndexError:
            self.index = 0
            raise StopIteration
        self.index += 1
        return result
    def is_equalset(self, other):
        return self.member_set == other.member_set
    def is_superset(self, other):
        return self.member_set.issuperset(other.member_set)
    def is_subset(self, other):
        return self.member_set.issubset(other.member_set)
    def member_union(self, other):
        return BlinkCluster(-1, list(self.member_set | other.member_set), dagLines=list(self.dag_line_set | other.dag_line_set))
    def member_intersection(self, other):
        return BlinkCluster(-1, list(self.member_set & other.member_set), dagLines=list(self.dag_line_set & other.dag_line_set))
    def member_difference(self, other):
        return BlinkCluster(-1, list(self.member_set - other.member_set), dagLines=list(self.dag_line_set - other.dag_line_set))
    def __hash__(self):
        return hash(tuple(sorted(self.cluster_members)))
    def __cmp__(self, other):
        return cmp(tuple(sorted(self.cluster_members)), tuple(sorted(other.cluster_members)))
    def is_single_copy(self):
        return self.noDupes

class SetOfClusters(object):
    def __init__(self, blink_clusters=None):
        if blink_clusters is None:
            blink_clusters = []
        #for iteration
        self.index = 0
        #BlinkCluster objects
        #in case blink_clusters is a set   
        blink_clusters = list(blink_clusters)
        if blink_clusters:
            if isinstance(blink_clusters[0], BlinkCluster):
                self.blink_clusters = blink_clusters
            else:
                raise TypeError('what is blink_clusters?')
        else:
            self.blink_clusters = []
        self.cluster_set = set(self.blink_clusters)
        #list with one tuple per cluster, containing the cluster_members
        self.cluster_member_tuples = [ tuple(sorted(clust.cluster_members)) for clust in self.blink_clusters ]
        #dictionary to find clusters indexed by their tuples
        clusterDict = {}
        for tup, clust in izip(self.cluster_member_tuples, self.blink_clusters):
            clusterDict[tup] = clust
        #a single set, with clusters (as tuples) as members 
        self.cluster_tuple_set = set(self.cluster_member_tuples)
    
    def get_cluster_by_member(self, memb):
        for clust in self.blink_clusters:
            if memb in clust:
                return clust
        return None

    def cluster_union(self, other):
        union = self.cluster_set | other.cluster_set
        l = list(union)
        return list(self.cluster_set | other.cluster_set)

    def cluster_intersection(self, other):
        return self.cluster_set & other.cluster_set
    
    def cluster_difference(self, other):
        return self.cluster_set - other.cluster_set

    def __len__(self):
        return len(self.blink_clusters)

    def __iter__(self):
        return self
    
    def next(self):
        try:
            result = self.blink_clusters[self.index]
        except IndexError:
            self.index = 0
            raise StopIteration
        self.index += 1
        return result
    
    def __str__(self):
        string = ''
        for c in sorted(self.blink_clusters, key=lambda x:x.number):
            string += '%s' % c
        return string

    '''
    def get_clusters_that_are_subsets_and_supersets(self, other):
        #first remove any identical clusters

        intersect = SetOfClusters([BlinkCluster(-1, members=list(c)) for c in self.cluster_intersection(other)])
        union = SetOfClusters([BlinkCluster(-1, members=list(c)) for c in self.cluster_union(other)])
        reduced1 = SetOfClusters([BlinkCluster(-1, members=list(c)) for c in self.cluster_difference(other)])
        reduced2 = SetOfClusters([BlinkCluster(-1, members=list(c)) for c in other.cluster_difference(self)])
        
        one = len(self)
        two = len(other)
        un = len(union)
        inter = len(intersect)
        only1 = len(reduced1)
        only2 = len(reduced2)
        print one, two, un, inter, only1, only2
        print inter / float(one), inter / float(two)
        exit()

        #print len(reduced1)
        #print len(reduced2)
        n1 = 0
        num = 0
        for clust1 in reduced1:
            n2 = 1
            n1 +=1 
            #print 'outer'
            for clust2 in reduced2:
                #print 'inner'
                #print n1, n2
                n2+=1
                if len(clust1.member_intersection(clust2) > 0:
                    if clust1.noDupes or clust2.noDupes:
                        if len(clust1.member_difference(clust2)) != 0 and len(clust2.member_difference(clust1)) != 0:
                            print 'not sub or super'
                        elif len(clust1) > len(clust2):
                            print 'subset'
                        else:
                            print 'superset'
                        
                        m1 = set(clust1)
                        m2 = set(clust2)
                        comb = sorted(list(m1 | m2))
                        for memb in comb:
                            if memb in clust1:
                                print num, memb,
                            else:
                                print num, '-',
                            if memb in clust2:
                                print memb
                            else:
                                print '-'
                        num += 1

        '''

def parse_mcl_output(filename):
    '''read MCL output, which looks like the below, return a list of BlinkClusters
    output is simply one line per cluster:
    OminuCC03S_FGT1789  OminuCC03S_FGT1792  OoffiCC03S_FGT1798  OminuBB03S_FGT0728  OminuBB03S_FGT0727  OoffiCC03S_FGT1799  OminuCC03S_FGT1791  OminuCC03S_FGT1790   
    '''
    lines = ( l.split() for l in open(filename, "rb") )
    allClusters = []

    num = 1
    for cluster in lines:
        try:
            allClusters.append(BlinkCluster(num, cluster))
            num = num + 1
        except:
            exit("problem converting mcl cluster to blink format")
    return allClusters

def parse_blink_output(filename, dagline_dict=None):
    '''read blink output, which looks like the below, return a list of BlinkClusters
    This indicates cluster 0 with one member, cluster 1 with 4, etc.
    0	ObartAA03S_FGT0005
    1	OglabAA03S_FGT0268
    1	OrufiAA03S_FGT0184
    1	OglabAA03S_FGT0269
    1	ObartAA03S_FGT0026
    2	OrufiAA03S_FGT0182
    2	OglabAA03S_FGT0266
    2	OminuCC03S_FGT0238
    '''
    lines = ( l.split() for l in open(filename, "rb") )
    allClusters = []
 
    clustDict = {}
    for line in lines:
        try:
            num, name = int(line[0]), line[1]
            if num in clustDict:
                clustDict[num].append(name)
            else:
                #if the number is a float
                if str(num) != line[0]:
                    raise Exception
                clustDict[num] = [ name ]
        except:
            print "problem reading line %s of blink.out\n" % (str(line))
            print "expecting lines with only:\ncluster# seqname\n"
            #my_output("problem reading line %s of blink.out\n" % (str(line)), logfile)
            #my_output("expecting lines with only:\ncluster# seqname\n", logfile)
            exit(1)
 
    for c in sorted(clustDict.iterkeys()):
        allClusters.append(BlinkCluster(c, clustDict[c], daglineDoubleDict=dagline_dict))
    return allClusters

'''
def blink_cluster_from_clique(thisClust, maxClique, mapping=None):
    if mapping is not None:
        new_members = []
        for member in clique:
            if mapping is not None:
                new_members.append(mapping[member]
            else:
                new_members.append(member)
'''
'''
def get_dagline_set_for_cluster(genes, daglineDoubleDict):
	clustHits = set()
	for tax1 in range(0, len(genes)):
		try:
			sub_dict = daglineDoubleDict[genes[tax1]]
		except:
			continue
		for tax2 in range(0, len(genes)):
			if tax1 != tax2:
				try:
					foundLine = sub_dict[genes[tax2]]
					clustHits.add('\t'.join(foundLine))
				except:
					continue
	return clustHits
'''

def get_dagline_set_for_cluster(genes, daglineDoubleDict):
    clustHits = set()
    for tax1 in range(0, len(genes)):
        names1 = [genes[tax1], re.sub('[.][0-9]$', '', genes[tax1])]
        #print 'names1', names1
        for n1 in names1:
            found = False
            if n1 in daglineDoubleDict:
                #print '\tfound n1:', n1
                sub_dict = daglineDoubleDict[n1]
                for tax2 in range(0, len(genes)):
                    if tax1 != tax2:
                        names2 = [genes[tax2], re.sub('[.][0-9]$', '', genes[tax2])]
                        #print '\tnames1', names1
                        for n2 in names2:
                            if n2 in sub_dict:
                                #print '\t\tfound n2:', n2
                                dl = sub_dict[n2]
                                if isinstance(dl, DagLine):
                                    clustHits.add(dl)
                                else:
                                    clustHits.add('\t'.join(dl))
                                #found = True
                                break
    return clustHits


def get_dagline_list_for_cluster(genes, daglineDoubleDict):
    #print 'dictsize', len(daglineDoubleDict)
    #print daglineDoubleDict.keys()
    clustHits = []
    for tax1 in genes:
        names1 = [tax1, re.sub('[.][0-9]$', '', tax1)]
        #print 'names1', names1
        for n1 in names1:
            found = False
            if n1 in daglineDoubleDict:
                #print '\tfound n1:', n1
                sub_dict = daglineDoubleDict[n1]
                for tax2 in genes:
                    if tax1 != tax2:
                        names2 = [tax2, re.sub('[.][0-9]$', '', tax2)]
                        #print '\tnames1', names1
                        for n2 in names2:
                            if n2 in sub_dict:
                                #print '\t\tfound n2:', n2
                                dl = sub_dict[n2]
                                #if 'glab' in n1:
                                #    print names1, names2
                                if isinstance(dl, DagLine):
                                    #if 'glab' in n1:
                                    #    print dl
                                    clustHits.append(dl)
                                else:
                                    clustHits.append('\t'.join(dl))
                                #found = True
                                break
    clustHits.sort()

    '''
    print 'added'
    for line in clustHits:
        if 'glab' in line.tax1:
            print line
    '''
    return clustHits


def get_dagline_double_dict(lineList, bidirectional=False):
    '''Create a dict with keys being query loci in dagchainer lines, and
    values being dicts with keys being the loci hit by the higher level
    loci.  Values of secondary dict are a list of strings for each element
    of the dagchainer line, or DagLine objects if that is what is passed in.
    
    lineList can be either a list of strings for each line, or a list
    of lists that already hold the individual fields of each line, or 
    DagLine objects.
    
    bidirectional means that the dict is indexed both by the query (line[1]) and hit (line[5]) seqs 
    - wait - bidirectional didn't make any sense here, and caused overwriting of earlier lines put
    into the dict.  Could make this work by having the second dict hold a list of lines, but don't need it right now

    dagchainer lines look like:
    rufipogon_3s    OrufiAA03S_FGT1690  1735    1735    glaberrima_3s   OglabAA03S_FGT1985  1972    1972    1e-199
    where numbers are coords of locus (in this case gene number) and the last value is e-value
    '''
    my_dict = {}
    if len(lineList) == 0:
        raise poo
        exit("get_dagline_double_dict passed empty list")
    if isinstance(lineList[0], str):
        lineList = [ line.split() for line in lineList ]
        print 'lineList', lineList
        if len(lineList[0][0]) == 1:
            exit("wtf")
    
    lineTups = []
    for line in lineList:
        if isinstance(lineList[0], DagLine):
            lineTups.append((line.tax1, line.tax2, line))
            if bidirectional:
                lineTups.append((line.tax2, line.tax1, line))
        else:
            lineTups.append((line[1], line[5], line))
            if bidirectional:
                lineTups.append((line[5], line[1], line))

    for t1, t2, line in lineTups:
        match = re.search('(.*)[.][0-9]*$', t1)
        if match:
            t1 = match.group(1)
        
        match = re.search('(.*)[.][0-9]*$', t2)
        if match:
            t2 = match.group(1)
      
        my_dict[t1].setdefault(t1, {})[t2] = line
        #if t1 in my_dict:
        #    my_dict[t1][t2] = line
        #else:
        #    my_dict[t1] = {t2 : line}
    return my_dict


def get_dagline_double_dict_from_dagline_objects(daglines):
    '''Create a dict with keys being query loci in dagchainer lines, and
    loci.  Values of secondary dict are a list of strings for each element
    of the dagchainer line.
    
    lineList can be either a list of strings for each line, or a list
    of lists that already hold the individual fields of each line
    
    dagchainer lines look like:
    rufipogon_3s    OrufiAA03S_FGT1690  1735    1735    glaberrima_3s   OglabAA03S_FGT1985  1972    1972    1e-199
    where numbers are coords of locus (in this case gene number) and the last value is e-value
    '''
    my_dict = {}
    if len(daglines) == 0:
        raise poo
        exit("get_dagline_double_dict_from_dagline_objects passed empty list")
    
    for line in daglines:
        t1, t2 = line.tax1, line.tax2
        
        match = re.search('(.*)[.][0-9]*$', t1)
        if match:
            t1 = match.group(1)
            
        match = re.search('(.*)[.][0-9]*$', t2)
        if match:
            t2 = match.group(1)
       
        my_dict.setdefault(t1, {})[t2] = line
        #if t1 in my_dict:
        #    my_dict[t1][t2] = line
        #else:
        #    my_dict[t1] = {t2 : line}
    return my_dict


class HitList(object):
    def __init__(self, hits):
        #self.hitlist = sets.Set(hits)
        self.hitlist = set(hits)
        self.uniqueNames = None
        self.numbersToNames = None
    
    def __len__(self):
        return len(self.hitlist)

    def get_sublist_by_query_names(self, names):
        #subset = sets.Set()
        subset = set()
        for hit in self.hitlist:
            for name in names:
                if name in hit[0]:
                    subset.add(hit)
        #return subset
        return HitList(subset)
        
    def get_sublist_by_hit_names(self, names):
        subset = set()
        for hit in self.hitlist:
            for name in names:
                if name in hit[1]:
                    subset.add(hit)
        return HitList(subset)

    def get_sublist_by_query_or_hit_names(self, names):
        subset = self.get_sublist_by_query_names(names)
        return subset.union(self.get_sublist_by_hit_names(names))
   
    def union(self, others):
        return HitList(self.hitlist.union(others.hitlist))

    def unique_names(self):
        if self.uniqueNames is None:
            count = 1
            self.uniqueNames = {}
            self.numbersToNames = {}
            for hit in self.hitlist:
                for name in hit:
                    if not name in self.uniqueNames:
                        self.uniqueNames[name] = count
                        self.numbersToNames[count] = name
                        count += 1
            if len(self.uniqueNames) != len(self.numbersToNames):
                exit("problem mapping hit names to numbers")
        return self.uniqueNames.keys()

    def output(self, stream=sys.stdout):
        for hit in self.hitlist:
            stream.write("%s\t%s\n" % hit)

    def get_list_numbers_for_names(self):
        if self.uniqueNames is None:
            self.unique_names()
        numSet = set()
        for hit in self.hitlist:
            #set.add((self.uniqueNames[hit[0]], self.uniqueNames[hit[1]]))
            numSet.add((self.uniqueNames[hit[0]], self.uniqueNames[hit[1]]))

    def output_for_dfmax(self, stream=sys.stdout):
        if self.uniqueNames is None:
            self.unique_names()

        stream.write('p EDGE %s %s\n' % (str(len(self.uniqueNames)), str(len(self.hitlist))))
        for hit in self.hitlist:
            stream.write('e %s %s\n' % (self.uniqueNames[hit[0]], self.uniqueNames[hit[1]]))


def parse_hits_file(filename):
    lines = [ tuple(l.split()) for l in open(filename, "rb") ]
    #return HitList(lines).get_sublist_by_query_names(['LOC'])
    return HitList(lines)


def make_dictionary_from_gff_arbitrary_field(string):
    mydict = {}
    fields = string.split(';')
    for f in fields:
        sep = f.split('=')
        try:
            mydict[sep[0]] = sep[1]
        except:
            exit("problem reading field, %s" % sep)
    return mydict


class ParsedSequenceDescription(object):
    def __init__(self, description=None, gff=None):
        '''
        OGE gff lines:
        >>> print ParsedSequenceDescription(gff='barthii_3s  ensembl gene    735328  738974  .   -   .   ID=ObartAA03S_FG0284;Name=ObartAA03S_FG0284;biotype=protein_coding').name
        ObartAA03S_FG0284
        >>> print ParsedSequenceDescription(gff='barthii_3s  ensembl mRNA    735328  738974  .   -   .   ID=ObartAA03S_FGT0284;Parent=ObartAA03S_FG0284;Name=ObartAA03S_FGT0284;biotype=protein_coding').name
        ObartAA03S_FGT0284
        >>> print ParsedSequenceDescription(gff='barthii_3s  ensembl CDS 738588  738974  .   -   0   Parent=ObartAA03S_FGT0284;Name=CDS.1419').name
        ObartAA03S_FGT0284
        
        OGE fasta sequence names
        >>> print ParsedSequenceDescription(description='ObartAA03S_FGT0284 seq=cds; coord=barthii_3s:735328..738974:-1; parent_gene=ObartAA03S_FG0284').name
        ObartAA03S_FGT0284
        >>> print ParsedSequenceDescription(description='>ObartAA03S_FG0284 seq=gene; coord=barthii_3s:735328..738974:-1').name
        ObartAA03S_FG0284
        
        IRGSP gff
        >>> print ParsedSequenceDescription(gff='Chr3    MSU_osa1r6  gene    934041  938212  .   -   .   ID=13103.t00151;Name=proteasome%20subunit%2C%20putative%2C%20expressed;Alias=LOC_Os03g02540').name
        LOC_Os03g02540
        >>> print ParsedSequenceDescription(gff='Chr3    MSU_osa1r6  mRNA    934041  938212  .   -   .   ID=13103.m00215;Parent=13103.t00151;Alias=LOC_Os03g02540.1').name
        LOC_Os03g02540.1
        >>> print ParsedSequenceDescription(gff='Chr3    MSU_osa1r6  CDS 937701  938087  .   -   0   Parent=13103.m00215').name
        13103.m00215
        
        IRGSP fasta sequence names
        >>> print ParsedSequenceDescription(description='>LOC_Os03g02540.1|13103.m00215|CDS proteasome subunit, putative, expressed').name
        LOC_Os03g02540.1
        >>> print ParsedSequenceDescription(description='>LOC_Os03g02540|13103.t00151|unspliced-genomic proteasome subunit, putative, expressed').name
        LOC_Os03g02540
        
        '''

        if gff and description:
            exit("pass either a gff or description string, not both")

        self.name = None
        self.ID = None
        self.description = None
        self.type = None
        self.molecule = None
        self.coord_start = None
        self.coord_end = None
        self.strand = None
        self.frame = None
        self.parent = None
        '''
        #############################
        OGE:

        CDS fasta description:
        >ObartAA03S_FGT0284 seq=cds; coord=barthii_3s:735328..738974:-1; parent_gene=ObartAA03S_FG0284

        gene fasta description
        >ObartAA03S_FG0284 seq=gene; coord=barthii_3s:735328..738974:-1

        gff for this looks like:
        barthii_3s  ensembl gene    735328  738974  .   -   .   ID=ObartAA03S_FG0284;Name=ObartAA03S_FG0284;biotype=protein_coding
        barthii_3s  ensembl mRNA    735328  738974  .   -   .   ID=ObartAA03S_FGT0284;Parent=ObartAA03S_FG0284;Name=ObartAA03S_FGT0284;biotype=protein_coding
        barthii_3s  ensembl intron  737785  738587  .   -   .   Parent=ObartAA03S_FGT0284;Name=intron.1408
        barthii_3s  ensembl intron  736782  737463  .   -   .   Parent=ObartAA03S_FGT0284;Name=intron.1409
        barthii_3s  ensembl intron  736578  736664  .   -   .   Parent=ObartAA03S_FGT0284;Name=intron.1410
        barthii_3s  ensembl intron  735818  736491  .   -   .   Parent=ObartAA03S_FGT0284;Name=intron.1411
        barthii_3s  ensembl intron  735508  735582  .   -   .   Parent=ObartAA03S_FGT0284;Name=intron.1412
        barthii_3s  ensembl exon    738588  738974  .   -   .   Parent=ObartAA03S_FGT0284;Name=ObartAA03S_FG0284.exon1
        barthii_3s  ensembl exon    737464  737784  .   -   .   Parent=ObartAA03S_FGT0284;Name=ObartAA03S_FG0284.exon2
        barthii_3s  ensembl exon    736665  736781  .   -   .   Parent=ObartAA03S_FGT0284;Name=ObartAA03S_FG0284.exon3
        barthii_3s  ensembl exon    736492  736577  .   -   .   Parent=ObartAA03S_FGT0284;Name=ObartAA03S_FG0284.exon4
        barthii_3s  ensembl exon    735583  735817  .   -   .   Parent=ObartAA03S_FGT0284;Name=ObartAA03S_FG0284.exon5
        barthii_3s  ensembl exon    735328  735507  .   -   .   Parent=ObartAA03S_FGT0284;Name=ObartAA03S_FG0284.exon6
        barthii_3s  ensembl CDS 738588  738974  .   -   0   Parent=ObartAA03S_FGT0284;Name=CDS.1419
        barthii_3s  ensembl CDS 737464  737784  .   -   0   Parent=ObartAA03S_FGT0284;Name=CDS.1420
        barthii_3s  ensembl CDS 736665  736781  .   -   0   Parent=ObartAA03S_FGT0284;Name=CDS.1421
        barthii_3s  ensembl CDS 736492  736577  .   -   0   Parent=ObartAA03S_FGT0284;Name=CDS.1422
        barthii_3s  ensembl CDS 735583  735817  .   -   2   Parent=ObartAA03S_FGT0284;Name=CDS.1423
        barthii_3s  ensembl CDS 735328  735507  .   -   0   Parent=ObartAA03S_FGT0284;Name=CDS.1424
        ######################################
        IRGSP:
        CDS fasta description:
        >LOC_Os03g02540.1|13103.m00215|CDS proteasome subunit, putative, expressed
        
        gene fasta description:
        >LOC_Os03g02540|13103.t00151|unspliced-genomic proteasome subunit, putative, expressed

        gff for this looks like:
        Chr3    MSU_osa1r6  gene    934041  938212  .   -   .   ID=13103.t00151;Name=proteasome%20subunit%2C%20putative%2C%20expressed;Alias=LOC_Os03g02540
        Chr3    MSU_osa1r6  mRNA    934041  938212  .   -   .   ID=13103.m00215;Parent=13103.t00151;Alias=LOC_Os03g02540.1
        Chr3    MSU_osa1r6  five_prime_UTR  938088  938212  .   -   .   Parent=13103.m00215
        Chr3    MSU_osa1r6  CDS 937701  938087  .   -   0   Parent=13103.m00215
        Chr3    MSU_osa1r6  CDS 936586  936906  .   -   0   Parent=13103.m00215
        Chr3    MSU_osa1r6  CDS 935789  935905  .   -   0   Parent=13103.m00215
        Chr3    MSU_osa1r6  CDS 935616  935701  .   -   0   Parent=13103.m00215
        Chr3    MSU_osa1r6  CDS 934712  934946  .   -   2   Parent=13103.m00215
        Chr3    MSU_osa1r6  CDS 934457  934636  .   -   0   Parent=13103.m00215
        Chr3    MSU_osa1r6  three_prime_UTR 934041  934456  .   -   .   Parent=13103.m00215

        '''
        #this gff reading attempt was aborted, I think
        if gff is not None:
            #gff's are generally the same, except for random junk in the last field.  
            #g = gff.replace(";", " ")
            split_gff = gff.split()
            #So, we end up with
            # 0          1        2       3        4     5   6   7      8  
            #Chr3    MSU_osa1r6  gene    3465    5944    .   +   .   ID=13103.t05666;Name=expressed%20protein;Alias=LOC_Os03g01008
            
            # 0             1     2     3       4    5   6   7      8                    
            #nivara_3s   ensembl CDS 1001307 1001549 .   -   0   Parent=OnivaAA03S_FGT0137;Name=CDS.26236
            self.molecule = split_gff[0]
            self.program = split_gff[1]
            self.type = split_gff[2]
            self.coord_start = split_gff[3]
            self.coord_end = split_gff[4]
            self.score = split_gff[5]
            self.strand = split_gff[6]

            self.various = make_dictionary_from_gff_arbitrary_field(split_gff[8])

            if self.type in [ 'gene', 'mRNA' ] :
                if 'Alias' in self.various:
                    self.name = self.various['Alias']
                elif 'Name' in self.various:
                    self.name = self.various['Name']
            else:
                try:
                    self.name = self.various['Parent']
                except:
                    exit("problem extracting name from %s" % self.various)
        else:
            desc = description.replace(";", " ")
            #desc = desc.replace(":", " ")
            split_desc = desc.split()
            if len(split_desc) < 3:
                exit('Description malformed? %s' % desc)
            
            #get the name
            self.name = split_desc[0].replace(">", "")

            #get the sequence type
            if not "seq" in split_desc[1]:
                exit("no \"seq\" found in %s" % description)
            match = re.search("seq=(.*)", split_desc[1])
            if match is None:
                exit("problem matching \"seq\" in %s" % description)
            self.type = match.group(1)
            
            #get molecule, coordinates and strand
            if not "coord" in split_desc[2]:
                exit("no \"coord\" found in %s" % description)
            match = re.search("coord=(.*):(.*):(.*)", split_desc[2])
            if match is None:
                exit("problem matching \"coord\" in %s" % description)
            self.molecule = match.group(1)
            coordSplit = match.group(2).split(".")
            (self.coord_start, self.coord_end) = (coordSplit[0], coordSplit[2])
            self.strand = match.group(3)

            #get parent gene
            if len(split_desc) > 3:
                #made some hasty changes here - check it through at some point
                if not "parent_gene" in split_desc[3]:
                    self.parent = 'none'
                    #exit("no \"parent_gene\" found in %s" % description)
                else:
                    match = re.search("parent_gene=(.*)", split_desc[3])
                    if match is None:
                        exit("problem matching \"parent_gene\" in %s" % description)
                    self.parent = match.group(1)
            else:
                #if this is a full gene, it has no parent
                self.parent = 'none'

    def output(self):
        print "name", self.name
        print "type", self.type
        print "molecule", self.molecule
        print "start", self.coord_start
        print "end", self.coord_end
        print "strand", self.strand
        print "parent", self.parent

if __name__ == "__main__":
    import doctest
    doctest.testmod()

