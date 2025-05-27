#!/usr/bin/env python3

import sys
import re
import argparse
import pprint
import subprocess
import json
from datasets import load_dataset
import argparse

from utils.logger import Logger
import utils.clause_validator as cval

# "folio_v2_validation.jsonl" # "folio_v2_train.jsonl" 


GKC_CMD = "gkc"
GKC_CMD_CONVERT = "gkc06"
TEMP_FILE_NAME = "tmpfile.txt"
DEBUG_PRINT=False
CONTINUE_ON_ERROR=True
SAVE_ERROR_FILES=True
MAX_NUM = -1
MIN_QUESTION_ID=-1

datafiles = {
  "v1": "folio-validation.jsonl",
  "v2": "folio_v2_validation.jsonl",
  "t2": "folio_v2_train.jsonl",
  "gt": "g-folio-train.jsonl",
  "gv": "g-folio-validation.jsonl"
}

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



import re

def replace_words_starting_with_number(input_string):
    """
    Replace words starting with a number in the input string with a modified format.
    For example, '2008SummerOlympics' becomes 'num2008_SummerOlympics'.
    
    Args:
    input_string (str): The string to process.

    Returns:
    str: The modified string.
    """
    # Regex to find words starting with numbers
    pattern = r'\b(\d+)(\w*)\b'
    
    # Replacement function to reformat matched words
    def replacer(match):
        number = match.group(1)  # Extract the leading number
        rest = match.group(2)  # Extract the rest of the word
        return f"n{number}_{rest}"  # Construct the replacement format

    # Use re.sub to replace all matches in the string
    return re.sub(pattern, replacer, input_string)



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
    # Logical Symbols
    el = el.replace(chr(8744), "|") # ∨ symbol
    el = el.replace(chr(8743), "&") # ∧ symbol
    el = el.replace(chr(172), "-") # ¬ symbol
    el = el.replace(chr(8594), "=>") # → symbol
    el = el.replace(chr(8853), "<~>") # ⊕ symbol
    el = el.replace(chr(8660), "<->") # ⇔ symbol
    el = el.replace(chr(8596), "<=>")  # ↔ symbol
    el = el.replace("—>", "=>")
    el = el.replace(chr(8800), "-") # ≠ symbol # TODO: Check T2 386, 387  (X=Y) is not correct clause
    el = el.replace("⟷", "<=>")

    # Spcial characters
    el = el.replace("Ś", "S") 
    el = el.replace("ś", "s")
    el = el.replace("ą", "a")
    el = el.replace("è", "e")
    el = el.replace("’", "_")
    el = el.replace(".", "_")
    el = el.replace("'", "_")
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
        
        cl = cval.verify_clause_syntax(cl)
            

        cl_new = replace_symbols(cl)
        cl_new = replace_words_starting_with_number(cl_new) 
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

    result = subprocess.run([GKC_CMD_CONVERT, "-convert", "-json", TEMP_FILE_NAME], capture_output=True, text=True)
    logic = result.stdout

    print("Logic", logic)

    logic = "\n".join(logic)
    logic = json.loads(logic)
    print(logic)

    return logic


# ---------- new stuff -----------

def process_folio(lines, only_ids=[]):

  lcount=0

  # print("Total lines: ", len(lines))

  for line in lines:

    if len(only_ids) > 0 and lcount not in only_ids:
      lcount+=1
      continue  

    # TODO: Remove later
    if MIN_QUESTION_ID > 0 and lcount < MIN_QUESTION_ID:
      lcount+=1
      print("Skipping")
      continue


    if DEBUG_PRINT: print()
    print("=== problem",lcount,"===")
    if DEBUG_PRINT: print("------ problem as text --------")
    
    data = json.loads(line)
    
    if "premises-FOL" in data:
      if DEBUG_PRINT: 
        print("premises-TXT:\n\t",data["premises"])
        print("Premises-FOL:\n\t",data["premises-FOL"])  
        
      premise_lst = data["premises-FOL"]
      if isinstance(premise_lst, str):
        [ print("\t", idx, "P:",p, ".") for idx, p in enumerate(premise_lst.split("\n")) ] 
        premise_lst = premise_lst.split("\n")

      premises = process_formlist(premise_lst)

      if DEBUG_PRINT: 
        print("Premises-Logic:")
        [ print("\t", idx, "L:",p, ".") for idx, p in enumerate(premises) ] 
    else:
      premises=None
    
    if "conclusion-FOL" in data:   
      if DEBUG_PRINT: 
        print("conclusion-TXT:\n\t",data["conclusion"])  
        print("Conclusion-FOL:\n\t",data["conclusion-FOL"])   

      tmp = fol_to_simple_logic(data["conclusion-FOL"])
      conclusion = tmp[1]

      if DEBUG_PRINT:   
        print("Conclusion-Logic:\n",conclusion)
    else:
      conclusion=None       

    if "label" in data:
      label=data["label"]
    else:
      label=None  

    if DEBUG_PRINT: 
      print("------ problem as input logic ------")   
      print("Premises:")
      [print("\t",p) for p in premises]
      print("Conclusion:\n\t",conclusion)
      print("Label:\n\t",label)
      print("------ proving ------")

    simpleproblem=make_positive_problem(premises,conclusion)
    if DEBUG_PRINT: 
      print("positive problem in simple format:")
      [print("\t",p.strip(), ".") for p in simpleproblem.split(".")]
    
    proverres=gkc_prove(simpleproblem, lcount)

    if DEBUG_PRINT: print("proverres for positive:",proverres,"\n")       
    
    if proverres!=True:
      simpleproblem=make_negative_problem(premises,conclusion)
      if DEBUG_PRINT: 
        print("negative problem in simple format:")
        [print("\t",p.strip(), ".") for p in simpleproblem.split(".")]
      proverres=gkc_prove(simpleproblem, lcount)
      if DEBUG_PRINT: print("proverres for negative:",proverres,"\n")
      if proverres==True:
        proverres=False
    
    if DEBUG_PRINT: print("* final result by prover:",proverres)    
    if DEBUG_PRINT: print("------ check for match with input label ------")

    if proverres==True: 
      txtres="True"
    elif proverres==False: 
      txtres="False"
    else: txtres="Uncertain"
    if label==txtres:
      print("Label corresponds to prover result.")
    else:
      print("* Label does not correspond to prover result.") 

    res = {
      "problem_id": lcount,
      "gold": label,
      "prover_res": txtres
    }       
    print("ans:", json.dumps(res))   

    lcount+=1
    if MAX_NUM > 0 and lcount >  MAX_NUM: break
 
  return

  res1=fol_to_simple_logic(clauses_str, upper_vars=[])
  print(res1)
  print("-- as sentences --")
  res2=make_formula_list(res1[1])
  for sentence in res2:
    print(sentence)

def make_positive_problem(premises,conclusion):
  for idx, p in enumerate(premises):
    if isinstance(p, list):
      premises[idx] = p[0]
    # print(f"\tPremise IDX={idx} {type(p)}: {p}")
  res = "\n".join(premises)
  nc="-("+conclusion+").\n"
  res=res+"\n"+nc
  return res

def make_negative_problem(premises,conclusion):
  for idx, p in enumerate(premises):
    if isinstance(p, list):
      premises[idx] = p[0]
    # print(f"\tPremise IDX={idx} {type(p)}: {p}")
  res="\n".join(premises)
  nc=conclusion+".\n"
  res=res+"\n"+nc
  return res

      
def process_formlist(lst, debug=False):
  res = []
  for idx, frm in enumerate(lst):
    tmp = fol_to_simple_logic(frm)
    sublst = make_formula_list(tmp[1])
    if len(sublst) > 0:
      # print("sublist", type(sublst))
      # print("restype1:", type(res))
      res.append(sublst) # res + sublst

    if debug:
      print(f"[{idx}:process_formlist]{frm}\n{'-'*80}\n")
      print("\ttmp:",tmp)
      print("\tsublst:",sublst)
      print("\tres:", res)
      make_formula_list(tmp[1], debug=True)

  return res  



def make_formula_list(frm, debug=False):
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
      # elif par == 1 and not binary_follow(frm,i+1):
      #   sentence=sentence.strip()
      #   sentence += ")."
      #   sentences.append(sentence)
      #  sentence = ""
    else:
      sentence+=c
    i+=1 

  if debug:
    print("Frm:", frm)
    print("Par:", par)
    
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



def gkc_prove(problemstr, question_id):
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
      
      if SAVE_ERROR_FILES:
        with open(f"errors/err_{question_id}.txt", "w") as f:
          f.write("Prover found an error in input:")
          f.write(resulttxt)
          f.write("\n")
          f.write("full prover input text where the error was found:")
          f.write(problemstr)

      # TODO: Remove ignore IDs later  
      # They are shifted by 1 because they are 0-indexed, e.g 49 is the 50th question
      ignore_ids = [49]
      if not CONTINUE_ON_ERROR:
        if question_id in ignore_ids: 
          return None
        else:
          print("Halting on question:", question_id)
        sys.exit(0)
      return None 
    else:       
       return None


clauses_str="""∃x (Project(x) ∧ Do(sam, x)) ∀x (Project(x) → (WrittenIn(x, cplusplus) ⊕ WrittenIn(x, python))) ∀x (Project(x) ∧ WrittenIn(x, python) ∧ Do(sam, x) → ¬Use(sam, mac)) Use(sam, mac) ∃x (Use(sam, mac) ∧ Song(x) → Play(sam, x)) ∀x (Song(x) ∧ Play(sam, x) → Titled(x, perfect))"""

clauses_str="""∀x (DrinkRegularly(x, coffee) → IsDependentOn(x, caffeine)) ∀x (DrinkRegularly(x, coffee) ∨ (¬WantToBeAddictedTo(x, caffeine))) ∀x (¬WantToBeAddictedTo(x, caffeine) → ¬AwareThatDrug(x, caffeine)) ¬(Student(rina) ⊕ ¬AwareThatDrug(rina, caffeine)) ¬(IsDependentOn(rina, caffeine) ⊕ Student(rina))"""

#clauses_str="""∃x (∀y (Project(x) ∧ Do(sam, y) → foo(y))) ∀x (DrinkRegularly(x, coffee)) dummy(a)""" 


if __name__ == "__main__":
    
    outfile = f"runlog.txt"
    logger = Logger(outfile)
    sys.stdout = logger  

    parser = argparse.ArgumentParser(description='Run FOLIO on GKC')
    parser.add_argument("df", choices=datafiles, help="Choose a result set")    
    parser.add_argument("--debug", action="store_true", help="Print debug info", default=False)
    parser.add_argument("--ids", help="Parse only ids")
    parser.add_argument("--min", help="Minimal question ID")
    
    args = parser.parse_args()
    DEBUG_PRINT=args.debug

    if args.min:
      MIN_QUESTION_ID=int(args.min)

    id_list = []
    if args.ids:
      id_list = args.ids.split(",")
      id_list = [ int(x) for x in id_list ]

    FOLIO_FILE = f"data/{datafiles[args.df]}"
    print("Process input:", FOLIO_FILE)

    f=open(FOLIO_FILE,"r")
    lines=f.readlines()
    f.close()
  
    process_folio(lines, only_ids=id_list)

