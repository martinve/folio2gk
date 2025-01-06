#!/usr/bin/env python3

import sys
import re
import argparse
import pprint
import subprocess
import json
from datasets import load_dataset

GKC_CMD = "gkc"
TEMP_FILE_NAME = "tmpfile.txt"

def extract_quantified_variables(logical_expression):
    """
    Extract variables defined by existential (\u2203) and universal (\u2200) quantifiers in a logical expression.

    Args:
        logical_expression (str): The logical expression as a string.

    Returns:
        dict: A dictionary with keys 'universal' and 'existential' containing lists of variables.
    """
    # Define patterns for universal and existential quantifiers
    universal_pattern = r"\u2200(\w+)"
    existential_pattern = r"\u2203(\w+)"

    # Find all variables associated with the quantifiers
    universal_vars = re.findall(universal_pattern, logical_expression)
    existential_vars = re.findall(existential_pattern, logical_expression)

    return {
        'u': universal_vars,
        'e': existential_vars
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
! [X] : ((Devices(X) & BelongTo(X, company)) => ConnectTo(X, googleHome)).
! [X] : ((Devices(X) & With(X, companyLogo)) => BelongTo(X, company)).
! [X] : ((Devices(X) => (With(X, companyLogo) <~> BelongTo(X, employee))).
! [X] : ((Devices(X) & BelongTo(X, employee)) => CanBeConnectedTo(X, wifi)).
! [X] : ((Devices(X) & ConnectTo(X, googleHome)) => ControlledBy(X, manager)).
! [X] : ((Devices(X) & CanBeConnectedTo(X, wifi)) => EasyToOperate(X)).
! [X] : ((Devices(X) & EasyToOperate(X)) => ProducedAfterNewCTOAppointed(X, company)).
Devices(modelXX) & (-ProducedAfterNewCTOAppointed(modelXX, company)).

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
        cl_new += "."
        new_clauses.append(cl_new)

    varlist = flatten_and_unique(varlist)

    ret = "\n".join(new_clauses)
    return varlist, ret


def logic_to_json(logic):
    
    with open("tmpfile.txt", "w") as f:
        f.write(logic)

    result = subprocess.run([GKC_CMD, "-convert", "-json", TEMP_FILE_NAME], capture_output=True, text=True)
    json_logic = result.stdout

    json_logic = eval(json_logic)
    json_logic = str(json_logic)
    json_logic = json_logic.replace("'", "\"")

    return json_logic


def extract_data(dataset, maxnum, parse_json=False):
    print("Train:", len(ds_train))
    print("Validation:", len(ds_valiation))
    print("---")

    for idx, it in enumerate(dataset):
        premises_fol = it["premises-FOL"]
        varlist, premises_logic = fol_to_simple_logic(premises_fol)

        conclusion_fol = it["conclusion-FOL"]
        _, conclusion_logic = fol_to_simple_logic(conclusion_fol, varlist)

        
        premises_json = None
        if parse_json:
            try:
                premises_json_str = logic_to_json(premises_logic)
                premises_json = json.loads(premises_json_str)
            except Exception as e:
                premises_json = "Error"

        print(f"[PREMISE]:\n{''.join(it['premises'])}\n")
        print(f"[PREMISE (FOL)]:\n{premises_fol}\n")
        print(f"[PREMISE (GK)]:\n{premises_logic}\n")
        if premises_json:
            print("[PREMISE (JSON-LD-LOGIC)]:")
            pprint.pprint(premises_json, compact=True)
            print()
        print(f"[CONCLUSION]:\n{''.join(it['conclusion'])}\n")  
        print(f"[CONCLUSION (FOL)]:\n{it['conclusion-FOL']}\n")
        print(f"[CONCLUSION (GK)]:\n{conclusion_logic}\n")
        print("\n===\n")
        

        if maxnum > 0 and idx >= maxnum - 1:
            break



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Prepare FOLIO tests')
    parser.add_argument("--max", type=int, default=-1, help="Max number of tests to run")
    parser.add_argument("--json", action="store_true", help="Parse simplified logic to JSON-LD-Logic")

    args = parser.parse_args()
    maxnum = args.max
    parse_json = args.json

    ds = load_dataset("tasksource/folio")
    ds_train = ds["train"]
    ds_valiation = ds["validation"]

    extract_data(ds_train, maxnum, parse_json)