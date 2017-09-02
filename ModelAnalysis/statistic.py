"""
Classes that compute statistics for SBML models.
Statistic is an abstract class. Leaf classes that inherit from Statistic
override the method getStatistic, which returns a dictionary that has
name-value pairs.
Usage for a non-abstract XStatistic that inherits from Statistic:
  x_statistic = XStatistic(shim)  # Where shim is a SBMLShim object
  statistic_dict = x_statistic.getStatistic()
Note that all leaf classes are assumed to be non-abstract statistics classes
that are to be instantiated.
"""
from sbml_shim import SBMLShim

import numpy as np
import re
import os.path
import pandas as pd
import sys

################################################
# Classes that collect statistics
################################################
class Statistic(object):
  """
  Abstract class for computing statistics. Leaf classes must implement
  gtStatistic. This class provides methods used by inheriting classes.
  """
  statistic_doc = {}  # Names with descriptions. Added by leaf classes.

  def __init__(self, shim):
    """
    :param SBMLShim shim:
    """
    self._shim = shim

  def getStatistic(self):
    """
    Collect statistics for the model.
    Must be overridden by another "collector" class.
    :return dict: Dictionary of statistic name and its mean, std
    """
    raise RuntimeError("Not implemented. Must override.")

  @classmethod
  def getNames(cls):
    """
    :return list-of-str: names of statistics
    """
    return cls.statistic_names

  @staticmethod
  def _findLeafSubclasses(klass):
    """
    Finds the descendents that have no inheritors
    :param type klass:
    :return list-of-type:
    """
    leaves = set()
    parents = set([klass])
    while len(parents) > 0:
      parent = parents.pop()
      children = parent.__subclasses__()
      if (len(children) == 0):
        leaves.add(parent)
      else:
        parents = parents.union(set(children))
    return leaves

  @classmethod
  def getAllStatistics(cls, shim):
    """
    Acquires all of the statistics available by instantiating all leaf
    classes.
    :param SBMLShim shim:
    :return dict: Dictionary of statistics
    """
    klasses = cls._findLeafSubclasses(cls)
    results = {}
    for klass in klasses:
      statistic = klass(shim)
      results.update(statistic.getStatistic())
    return results

  @staticmethod
  def _jointSubstring(substrings, string):
    """
    Calculates the number of non-overlapping substrings in string.
    The approach is heuristic and so will not always find the maximum
    number of substrings.
    :param list-of-str substrings:
    :param str string:
    :return int: Number of non-overlapping substrings present
    """
    ranges = []  # Positions for reactants in product
    for substring in substrings:
      pos = string.find(substring)
      if pos >= 0:
        ranges.append(range(pos, len(substring)))
    result = 0
    if len(ranges) > 0:
      result = 1
      last_range = set(ranges[0])
      for rng in ranges[1:]:
        combined_range = last_range.union(set(rng))
        if len(combined_range) == len(last_range) + len(rng):
          result += 1
          last_range = combined_range
    return result


################################################
# Model statistics
################################################
class ModelStatistic(Statistic):
  """
  Computes statistics that apply to the entire model
  """
  NUM_REACTIONS = "Num_Reactions"
  statistic_doc[NUM_REATIONS] = "Number of reactions in the model"
  NUM_PARAMETERS = "Num_Parameters"
  statistic_doc[NUM_PARAMETERS] = "Number of parameters in the model"
  NUM_SPECIES = "Num_Species"
  statistic_doc[NUM_SPECIES] = "Number of species in the model"


  def getStatistic(self):
    """
    :return dict:
    """
    return   {
              NUM_REACTIONS: len(self._shim.getReactionIndicies()),
              NUM_PARAMETERS: len(self._shim.getParameterNames()),
              NUM_SPECIES: len(self._shim.getSpecies()),
             }


################################################
# Reaction statistics
################################################
class ReactionStatistic(Statistic):
  """
  Abstract class for collecting complex reaction statistics. Reaction statistics
  are obtained by iterating across all reactions and then computing
  aggregations of the results.
  Classes that inherit must provide the following methods:
    _getValues(dict, idx) - provides a scalar number for a reaction, where
        dict is an initially empty dictionary, idx is the reaction index
  """

  def getStatistic(self):
    """
    Compute statistics for the reactions
    :return dict:
    """
    indicies = self._shim.getReactionIndicies()
    value_dict = {}
    for idx in indicies:
      value_dict = self._addValues(value_dict, idx)
    result = {}
    for key in value_dict.keys():
      mean_key = "%s_mean" % key
      result[mean_key] = np.mean(value_dict[key])
      std_key = "%s_std" % key
      result[std_key] = np.std(value_dict[key])
    return result

  staticmethod
  def _addElementToListInDict(a_dict, key, value):
    """
    Adds an element to a list entry in a dictionary.
    """
    if not key a_dict:
      a_dict[key] = [value]
    else:
      a_dict[key].append(value)

  def _addValues(self, value_dict, idx):
    """
    :param dict value_dict:
    :param int idx: index of a reaction
    :return dict: updates the value dictionary
    """
    raise RuntimeError("Must override.")


class SimpleReactionStatistic(Statistic):
  """
  Computes simple statistics for reactions.
  """
  NUM_REACTANTS = "Num_Reactants"
  statistic_doc[NUM_REACTANTS] = "Mean (_mean) and std (_std) "  \
      + "of the number of reactants in a reaction in the model"
  NUM_PRODUCTS = "Num_Products"
  statistic_doc[NUM_PRODUCTS] = "Mean (_mean) and std (_std) "  \
      + "of the number of products in a reaction in the model"

  def _addValues(self, value_dict, idx):
    """
    :param dict value_dict:
    :param int idx: index of a reaction
    :return dict: updates the value dictionary
    """
    cls = self.__class__
    num_reactants = len([r.getSpecies() for
                         r in self._shim.getReactants(reaction_idx)])
    num_products = len([p.getSpecies() for
                        p in self._shim.getProducts(reaction_idx)])
    cls._addElementToListInDict(value_dict, cls.NUM_REACTANTS, num_reactants)
    cls._addElementToListInDict(value_dict, cls.NUM_PRODUCTS, num_products)
    return value_dict
    

class ComplexTransformationReactionStatistic(ReactionStatistic)
  """
  Determines if the reactants are combined in a way to be a substring
  of the product.
  """
  COMPLEX_FORMATION = "Complex_Formation"
  statistic_doc[COMPLEX_FORMATION] = "Mean (_mean) and std (_std) "  \
      + "of the number of reactions in which two reactants form a product"
  COMPLEX_DISASSOCIATION = "Complex_Disassociation"
  statistic_doc[COMPLEX_DISASSOCIATION] = "Mean (_mean) and std (_std) "  \
      + "of the number of reactions in which one reactant forms two or more products"

  def _getValues(self, value_dict, reaction_idx):
    """
    Looks for a combination of the reactants in a product.
    :param int reaction_idx:
    :return value_dict:
    """
    cls = self.__class__
    reactants = [r.getSpecies() for
                 r in self._shim.getReactants(reaction_idx)]
    products = [p.getSpecies() for
                 p in self._shim.getProducts(reaction_idx)]
    result = 0
    if len(reactants) > 1 and len(products) > 0:
      for product in products:
        if self.__class__._jointSubstring(reactants, product) > 1:
          result = 1
          break
    cls._addElementToListInDict(value_dict, cls.COMPLEX_FORMATION, result)
    result = 0
    for reactant in reactants:
      if self._jointSubstring(products, reactant) > 1:
        result = 1
        break
    cls._addElementToListInDict(value_dict, cls.COMPLEX_DISASSOCIATION, result)
    return value_dict


if __name__ == '__main__':
  main(sys.argv)  
