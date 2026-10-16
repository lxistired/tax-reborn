"""Finite consumer of explicitly resolved MC leaf InstanceValues.

This module does not supply the active InstanceValue vector, ancestors, cache,
filter or final MEF key. The request wrapper derives one known source candidate
and labels its result conditional. It never treats that candidate as the whole
native vector.
"""
from dataclasses import dataclass

@dataclass(frozen=True)
class LeafInstance:
    xpath: bytes
    payload: object

class AmbiguousLeafInstances(ValueError):
    """Owned equivalent of the native InvalidStateException cardinality branch."""

def filter_indices(values, query):
    if type(values)is not tuple or len(values)>128 or type(query)is not bytes or len(query)>4096:
        raise ValueError('Bounded explicit leaf instances and length-delimited byte query required')
    chosen=[]
    for index,row in enumerate(values):
        if type(row)is not LeafInstance or type(row.xpath)is not bytes or len(row.xpath)>4096:
            raise ValueError('Explicit length-delimited Instance XPath required')
        # Original checks a prefix at position0, then exact full-path duplicates.
        # It does not test Used, HasValue, Error, flags or text/payload equality.
        if row.xpath.startswith(query)and not any(values[i].xpath==row.xpath for i in chosen):
            chosen.append(index)
    return tuple(chosen)

def select_leaf(values, query):
    selected=filter_indices(values,query)
    if len(selected)>1:raise AmbiguousLeafInstances('Multiple distinct leaf instance paths; native branch constructs InvalidStateException')
    return None if not selected else values[selected[0]]

@dataclass(frozen=True)
class ErrorScalar:
    flagword: int

@dataclass(frozen=True)
class ErrorMC:
    flagword: int
    children: tuple

def get_error(value):
    """Actual v140 reduction: own base bit first, then children recursively.

    Blank, Used, Override and key bytes do not suppress Error. Native does not
    impose this module's finite depth/node limits; no native cyclic graph claim
    is made. All objects here are owned diagnostics, not native cache snapshots.
    """
    count=0;active=set()
    def visit(item,depth):
        nonlocal count
        count+=1
        if count>1024 or depth>128:raise ValueError('Finite Error graph bound exceeded')
        if type(item)not in(ErrorScalar,ErrorMC)or type(item.flagword)is not int or not 0<=item.flagword<1<<64:
            raise ValueError('Explicit finite Value base flagword required')
        if item.flagword&4:return True
        if type(item)is ErrorScalar:return False
        if type(item.children)is not tuple or len(item.children)>128:raise ValueError('Bounded explicit nonNULL children required')
        if id(item)in active:raise ValueError('Cyclic owned Error graph refused')
        active.add(id(item))
        try:return any(visit(child,depth+1)for child in item.children)
        finally:active.remove(id(item))
    return visit(value,0)
