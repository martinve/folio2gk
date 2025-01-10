#!/usr/bin/env python3

import sys
import re
import argparse
import pprint
import subprocess
import json
from datasets import load_dataset

FOLIO_FILE="folio-validation.jsonl"
GKC_CMD = "./gkc"
TEMP_FILE_NAME = "tmpfile.txt"
DEBUG_PRINT=False
CONTINUE_ON_ERROR=True

def extract_and_rewrite_quantifiers(logic_statement):
    """
    Extracts variables defined by existential and universal quantifiers and rewrites the statement.

    Args:
        logic_statement (str): The logical expression.

    Returns:
        dict: A dictionary with existential and universal variables.
        str: The rewritten logical statement with quantifier wrapping.
    """
    # Regular expressions to match quantifiers
    universal_pattern = r"\u2200(\w+)"  # Matches ∀ (∀) followed by a variable
    existential_pattern = r"\u2203(\w+)"  # Matches ∃ (∃) followed by a variable

    # Extract variables defined by universal and existential quantifiers
    universal_vars = re.findall(universal_pattern, logic_statement)
    existential_vars = re.findall(existential_pattern, logic_statement)

    # Rewrite the logic statement
    rewritten_statement = re.sub(universal_pattern, r"! [\1] :", logic_statement)
    rewritten_statement = re.sub(existential_pattern, r"? [\1] :", rewritten_statement)

    return {
        "u_vars": universal_vars,
        "e_vars": existential_vars
    }, rewritten_statement


def transform_variables_to_uppercase(logic_statement, variables):
    """
    Transforms all occurrences of specified variables in the logic statement to uppercase.

    Args:
        logic_statement (str): The logical expression.
        variables (list): List of variable names to transform.

    Returns:
        str: The logic statement with variables transformed to uppercase.
    """
    for var in variables:
        logic_statement = re.sub(rf"\b{var}\b", var.upper(), logic_statement)
    return logic_statement


def replace_symbols(el):
    el = el.replace(chr(8744), "|") # ∨ symbol
    el = el.replace(chr(8743), "&") # ∧ symbol
    el = el.replace(chr(172), "-") # ¬ symbol
    el = el.replace(chr(8594), "=>") # → symbol
    el = el.replace(chr(8853), "<~>") # ⊕ symbol
    return el


def replace_quantifiers(clause, upper_vars=[]):

    vars, new_clause = extract_and_rewrite_quantifiers(clause)
    varlist = sorted({x for v in vars.values() for x in v})
    varlist += upper_vars
    varlist = list(set(varlist))
    if varlist:
        new_clause = transform_variables_to_uppercase(new_clause, varlist)
    return varlist, new_clause


def flatten_and_unique(nested_list):
    """
    Flattens a nested list and returns a list of unique values.

    Args:
        nested_list (list of lists): The nested list to flatten.

    Returns:
        list: A list of unique values sorted alphabetically.
    """
    # Flatten the list
    flattened = [item for sublist in nested_list for item in sublist]
    # Return unique values as a sorted list
    return sorted(set(flattened))

def fol_to_simple_logic(clauses_str, upper_vars=[]):
    """
    Convert a FOL clauses to a simplified logic clauses to be run on GK.

    Args:
        clauses_str (str): The FOL clauses as a string.
        upper_vars (list): List of variables to transform to uppercase.

    Returns:
        list: A list of variables to be converted to uppercase
        str: The simplified logic clauses.

    """
    clauses = clauses_str.split("\n")
    new_clauses = []
    varlist = []
    for cl in clauses:
        cl_new = replace_symbols(cl)
        vars, cl_new = replace_quantifiers(cl_new, upper_vars)
        if vars:
            varlist.append(vars)
        #cl_new += "."
        new_clauses.append(cl_new)

    varlist = flatten_and_unique(varlist)

    ret = "\n".join(new_clauses)
    return varlist, ret


def logic_to_json(logic):
    print("Logic", logic)
    
    with open("tmpfile.txt", "w") as f:
        f.write(logic)

    result = subprocess.run([GKC_CMD, "-convert", "-json", TEMP_FILE_NAME], capture_output=True, text=True)
    logic = result.stdout

    print("Logic", logic)

    logic = "\n".join(logic)
    logic = json.loads(logic)
    print(logic)

    return logic


# ---------- new stuff -----------

def process_folio():
  fname=FOLIO_FILE
  f=open(fname,"r")
  lines=f.readlines()
  f.close()
  lcount=0
  for line in lines:
    if DEBUG_PRINT: print()
    print("=== problem",lcount,"===")
    if DEBUG_PRINT: print("------ problem as text --------")
    data=json.loads(line)
    if "premises-FOL" in data:
       if DEBUG_PRINT: print("premises",data["premises"])  
       premises=process_formlist(data["premises-FOL"])
    else:
       premises=None
    if "conclusion-FOL" in data:   
       if DEBUG_PRINT: print("conclusion",data["conclusion"])   
       tmp=fol_to_simple_logic(data["conclusion-FOL"])
       conclusion=tmp[1]
    else:
       conclusion=None       
    if "label" in data:
       label=data["label"]
    else:
       label=None         
    if DEBUG_PRINT: 
      print("------ problem as input logic ------")   
      print("premises",premises)
      print("conclusion",conclusion)
      print("label",label)
      print("------ proving ------")
    simpleproblem=make_positive_problem(premises,conclusion)
    if DEBUG_PRINT: print("positive problem in simple format:\n",simpleproblem)
    proverres=gkc_prove(simpleproblem)
    if DEBUG_PRINT: print("proverres for positive:",proverres,"\n")       
    if proverres!=True:
      simpleproblem=make_negative_problem(premises,conclusion)
      if DEBUG_PRINT: print("negative problem in simple format:\n",simpleproblem)
      proverres=gkc_prove(simpleproblem)
      if DEBUG_PRINT: print("proverres for negative:",proverres,"\n")
      if proverres==True:
         proverres=False
    if DEBUG_PRINT: print("* final result by prover:",proverres)    
    if DEBUG_PRINT: print("------ check for match with input label ------")
    if proverres==True: txtres="True"
    elif proverres==False: txtres="False"
    else: txtres="Uncertain"
    if label==txtres:
      print("Label corresponds to prover result.")
    else:
      print("* Label does not correspond to prover result.")            
    lcount+=1
    #if lcount>5: break
  return

  res1=fol_to_simple_logic(clauses_str, upper_vars=[])
  print(res1)
  print("-- as sentences --")
  res2=make_formula_list(res1[1])
  for sentence in res2:
    print(sentence)

def make_positive_problem(premises,conclusion):
   res="\n".join(premises)
   nc="-("+conclusion+").\n"
   res=res+"\n"+nc
   return res

def make_negative_problem(premises,conclusion):
   res="\n".join(premises)
   nc=conclusion+".\n"
   res=res+"\n"+nc
   return res

      
def process_formlist(lst):
  res=[]
  for frm in lst:
    tmp=fol_to_simple_logic(frm)
    sublst=make_formula_list(tmp[1])
    res=res+sublst
  return res  



def make_formula_list(frm):
  #print("frm",frm)
  i=0
  res=""
  par=0
  sentences=[]
  sentence=""
  while(i<len(frm)):
    c=frm[i]
    if c=="(":
      par+=1
      sentence+=c
    elif c==")":
      par-=1
      sentence+=c
      if par==0 and not binary_follow(frm,i+1):
        sentence=sentence.strip()
        sentence+="."
        sentences.append(sentence)
        sentence=""
    else:
     sentence+=c
    i+=1 
  return sentences       

     
def binary_follow(s,i):
  while(i<len(s)):
    c=s[i]
    if c in ["&","V","v","<"]:
       return True
    elif c in [" ","\t"]:
       pass
    else:
       return False
    i+=1
  return False  



def gkc_prove(problemstr):
    #print("problemstr", problemstr)    
    with open("tmpfile.txt", "w") as f:
        f.write(problemstr)
    result = subprocess.run([GKC_CMD, TEMP_FILE_NAME, "-print", "10", "-seconds", "1"], capture_output=True, text=True)
    resulttxt = result.stdout
    #print("resulttxt", resulttxt)
    if "proof not found" in resulttxt:
      return None
    elif "proof found" in resulttxt:
      return True
    elif "error" in resulttxt:
      print("Prover found an error in input:",resulttxt)
      print("full prover input text where the error was found:\n",problemstr)
      if not CONTINUE_ON_ERROR:
        sys.exit(0)
      return None 
    else:       
       return None


clauses_str="""∃x (Project(x) ∧ Do(sam, x)) ∀x (Project(x) → (WrittenIn(x, cplusplus) ⊕ WrittenIn(x, python))) ∀x (Project(x) ∧ WrittenIn(x, python) ∧ Do(sam, x) → ¬Use(sam, mac)) Use(sam, mac) ∃x (Use(sam, mac) ∧ Song(x) → Play(sam, x)) ∀x (Song(x) ∧ Play(sam, x) → Titled(x, perfect))"""

clauses_str="""∀x (DrinkRegularly(x, coffee) → IsDependentOn(x, caffeine)) ∀x (DrinkRegularly(x, coffee) ∨ (¬WantToBeAddictedTo(x, caffeine))) ∀x (¬WantToBeAddictedTo(x, caffeine) → ¬AwareThatDrug(x, caffeine)) ¬(Student(rina) ⊕ ¬AwareThatDrug(rina, caffeine)) ¬(IsDependentOn(rina, caffeine) ⊕ Student(rina))"""

#clauses_str="""∃x (∀y (Project(x) ∧ Do(sam, y) → foo(y))) ∀x (DrinkRegularly(x, coffee)) dummy(a)""" 


if __name__ == "__main__":
    process_folio()
   

    #jres=logic_to_json(res)
    #print(jres)
    