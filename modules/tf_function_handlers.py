from ast import literal_eval
from contextlib import suppress
from itertools import product

from modules.postfix import Conversion, Evaluate


def resolve_nested_functions(param):
    from modules.helpers import check_for_tf_functions, find_between, fix_lists

    while check_for_tf_functions(param) != False:
        no_change = param
        function_name = check_for_tf_functions(param)
        func_param = str(find_between(param, f"{function_name}(", ")"))
        # TODO: Handle for loops in parameters of
        if "[for" in func_param:
            func_param = find_between(func_param, "[for", ":", "[", True)
            func_param = find_between(func_param, ":", "]", "", True)
        if "*.id," in func_param:
            id_str = find_between(param, "aws_", ".id")
            new_param = func_param.replace("aws_" + id_str + ".id", "[]")
            eval_result = str(getattr(tf_function_handlers, function_name)(new_param))
        else:
            if func_param != None:
                eval_result = str(
                    getattr(tf_function_handlers, function_name)(func_param)
                )
            else:
                eval_result = "[]"
        param = param.replace(f"{function_name}(" + func_param + ")", str(eval_result))
        param = fix_lists(param)
        if param == no_change and check_for_tf_functions(param) != False:
            print(f"   ERROR: Unable to resolve parameter {function_name}({param})")
            break
    if "?" in param and ":" in param:
        obj = Conversion(len(param))
        pf = obj.infixToPostfix(param)
        obj = Evaluate(len(pf))
        eval_value = obj.evaluatePostfix(pf)
        if eval_value == "" or eval_value == " ":
            eval_value = 0
        param = eval_value
    if "[for" in param:
        param = find_between(param, "[for", ":", "[", True)
        param = find_between(param, ":", "]", "", True)
    if "None" in param:
        param = param.replace("None", "")
    return param.strip()


class tf_function_handlers:
    def contains(param):
        param = resolve_nested_functions(param)
        if "],'" or '],"' in param:
            param_list = param.split(",")
            listofvals = literal_eval(param_list[0])
        if param_list[1].replace('"', "") in listofvals:
            return True
        else:
            return False

    def regexall(param):
        param = resolve_nested_functions(param)
        params = param.split(",")
        print(params)

    def concat(param):
        param = resolve_nested_functions(param)
        params = param.split("],")
        final_list = []
        for index, value in enumerate(params):
            if not value.endswith("]"):
                value = value + "]"
            value = literal_eval(value)
            if index == 0:
                final_list = value
            else:
                final_list.extend(value)
        return final_list

    def distinct(param):
        if param == "" or param == "[]":
            return "[]"
        param = resolve_nested_functions(param)
        paramlist = literal_eval(param)
        unique_list = list(dict.fromkeys(paramlist))
        return unique_list

    def element(param):
        param = resolve_nested_functions(param)
        if param == "[]" or param == "" or param == '""':
            return ""
        p = literal_eval(param)
        # TODO: Find out which element needs to be returned instead of defaulting to zero
        return p[0]

    def coalescelist(param):
        param = resolve_nested_functions(param)
        if param == "[]" or param == "" or param == '""':
            return ""
        p = literal_eval(param)
        # TODO: Find out which element needs to be returned instead of defaulting to zero
        if p[0]:
            return p[0]
        else:
            return p[1]

    def flatten(param):
        param = resolve_nested_functions(param)
        paramlist = literal_eval(param)
        flat_list = []
        for subitem in paramlist:
            if isinstance(subitem, list):
                for item in subitem:
                    flat_list.append(item)
            else:
                flat_list.append(subitem)
        return flat_list

    def length(param):
        from modules.helpers import fix_lists

        param = resolve_nested_functions(param)
        if param == "[]" or param == "" or param == '""':
            return 0
        # if param.startswith("data.") or param.startswith("local."):
        #     return 0
        if param == "True" or param == "False" or param == "None":
            return 0
        if param.isnumeric():
            return int(param)
        if (
            param.startswith('"[')
            or param.startswith('"{')
            or param.startswith("[")
            or param.startswith("{")
        ):
            if param.startswith('"'):
                param = param.replace('"', "")
            return len(literal_eval(param))

    def keys(param):
        param = resolve_nested_functions(param)
        if param.startswith("[") or param.startswith("{"):
            param = literal_eval(param)
        else:
            return "None"
        if isinstance(param, list):
            param = param[0]
        return list(param.keys())

    def lookup(param):
        return "None"

    def max(param):
        param = resolve_nested_functions(param)
        param = param.replace(",,", ",0,")
        if param.endswith(","):
            param = param[0:-1]
        paramlist = literal_eval(param)
        return max(paramlist)

    def replace(param):
        param = resolve_nested_functions(param)
        paramlist = param.split(",")
        return paramlist[0].replace(paramlist[1], paramlist[2])

    def setproduct(param):
        param = resolve_nested_functions(param)
        paramlist = literal_eval(param)
        return list(product(*paramlist))
