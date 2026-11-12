"""Small explicit analysis rules, also tested on boundary cases."""
import itertools,math

def safe_ratio(numerator,denominator):
 return None if denominator==0 else numerator/denominator

def cohort_rate(returning,size,complete):
 return safe_ratio(returning,size) if complete else None

def shapley(base,current):
 result=[0.0]*len(base)
 perms=list(itertools.permutations(range(len(base))))
 for order in perms:
  state=list(base)
  for i in order:
   previous=math.prod(state);state[i]=current[i]
   result[i]+=(math.prod(state)-previous)/len(perms)
 return result
