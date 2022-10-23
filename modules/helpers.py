from ast import literal_eval
from contextlib import suppress
import click
import re
import os
from modules.tf_function_handlers import tf_function_handlers
from sys import exit

reverse_arrow_list = [
    'aws_route53',
    'aws_cloudfront',
    'aws_vpc.',
    'aws_subnet.',
    'aws_iam_role.',
    'aws_lb',
]

implied_connections = {'certificate_arn': 'aws_acm_certificate'}


def check_for_domain(string: str) -> bool:
    exts = ['.com', '.net', '.org', '.io', '.biz']
    for dot in exts:
        if dot in string:
            return True
    return False

def url(string: str) -> str:
    if string.count('://') == 0:
        return 'https://' + string
    return string

def check_for_tf_functions(string):
    for tf_function in dir(tf_function_handlers):
        if tf_function + '(' in string and 'ERROR!_' + tf_function not in string:
            return tf_function
    return False


def find_nth(string, substring, n):
    if (n == 1):
        return string.find(substring)
    else:
        return string.find(substring, find_nth(string, substring, n - 1) + 1)


def find_between(text,begin,end,alternative='',replace=False,occurrence=1):
    if not text:
        return
    # Handle Nested Functions with multiple brackets in parameters
    if begin not in text and not replace:
        return ''
    elif begin not in text and replace:
        return text
    if end == ')':
        begin_index = text.find(begin)
        # begin_index = find_nth(text, begin, occurrence)
        end_index = find_nth(text, ')', occurrence)
        end_index = text.find(')', begin_index)
        middle = text[begin_index + len(begin):end_index]
        num_brackets = middle.count('(')
        if num_brackets >= 1:
            end_index = find_nth(text, ')', num_brackets + 1)
            middle = text[begin_index + len(begin):end_index]
        return middle
    else:
        middle = text.split(begin, 1)[1].split(end, 1)[0]
    # If looking for a space but no space found, terminate with any non alphanumeric char except _
    # so that variable names don't get broken up (useful for extracting variable names and locals)
    if (end == ' ' or end == '') and not middle.endswith(' '):
        for i in range(0, len(middle)):
            char = middle[i]
            if not char.isalpha() and char != '_' and char != '-':
                end = char
                middle = text.split(begin, 1)[1].split(end, 1)[0]
                break
    if (replace):
        return text.replace(begin + middle, alternative, 1)
    else:
        return middle


def handle_conditionals(statement, all_locals, all_variables, filename):
    statement = fix_lists(statement)
    while 'var.' in statement:
        statement = replace_variables(statement,filename,all_variables)
    while 'local.' in statement:
        statement = resolve_locals(statement, all_locals)
    while check_for_tf_functions(statement) != False:
        statement = eval_tf_functions(statement)
        statement = fix_lists(statement)
    return statement


def eval_tf_functions(eval_string):
    # function_name = check_for_tf_functions(eval_string)
    # Find out how many occurances of functions called within functions exist here so we know where to terminate brackets
    function_name = check_for_tf_functions(eval_string)
    # Determine startpos of function parameter
    startpos = eval_string.find(function_name+'(') + len(function_name)
    rhs = eval_string[startpos+1:len(eval_string)]
    endpos = rhs.find(')')
    middle = rhs[0:endpos]
    if '(' in middle :
        # We have nested fucnctions
        # get right hand side of statement
        ob = False
        cb = False
        for i in range(len(rhs)):
            if rhs[i] == '(' :
                ob = True
            if rhs[i] == ')' :
                cb = True
                if ob == True :
                    ob = False
                    cb = False
                else :
                    middle = rhs[0:i]
                    endpos = i
                    break
    func_param = middle
    eval_result = None
    with suppress(Exception):

        eval_result = str(getattr(tf_function_handlers, function_name)(func_param))
    if not eval_result:
        click.echo(
            f'    WARNING: Unable to evaluate {function_name}({func_param})')
        eval_result = f'ERROR!_{function_name}(' + func_param + ')'
    eval_string = eval_string.replace(f'{function_name}(' + func_param + ')',str(eval_result))
    eval_string = fix_lists(eval_string)
    return eval_string


def resolve_locals(eval_string, all_locals):
    local_found_list = re.findall("local\.[A-Za-z0-9_-]+", eval_string)
    if len(local_found_list) > 0:
        for local_var in local_found_list:
            local_var = local_var.split('local.')[1]
            # local_var = str(find_between(eval_string, 'local.', ' '))
            # We need to interpolate local variable value
            for file, localvalues in all_locals.items():
                if local_var in localvalues:
                    resolved_local = localvalues[local_var]
                    resolved_local = fix_lists(resolved_local)
                    eval_string = eval_string.replace('local.' + local_var,
                                                      resolved_local)
                    eval_string = fix_lists(eval_string)
    return eval_string


def pretty_name(name: str, show_title=True) -> str:
    '''
        Beautification for AWS Labels
    '''
    resourcename = ''
    if 'null_' in name or 'random' in name or 'time_sleep' in name:
        return 'Null'
    else:
        name = name.replace('aws_', '')
    servicename = name.split('.')[0]
    service_label = name.split('.')[-1]
    if servicename == 'route_table_association':
        servicename = 'Route Table'
    if servicename == 'ecs_service_fargate':
        servicename = 'Fargate'
    if servicename == 'instance':
        servicename = 'ec2'
    if servicename == 'lambda_function':
        servicename = ''
    if servicename == 'iam_role':
        servicename = 'role'
    if servicename == 'dx':
        servicename = 'Direct Connect'
    if servicename == 'iam_policy':
        servicename = 'policy'
    if resourcename == 'this':
        resourcename = ''
    if servicename[0:3] in [
            'acm', 'ec2', 'kms', 'elb', 'nlb', 'efs', 'ebs', 'iam', 'api',
            'acm', 'ecs', 'rds', 'lb', 'alb', 'elb', 'nlb', 'nat'
    ]:
        acronym = servicename[0:3]
        servicename = servicename.replace(acronym, acronym.upper())
        servicename = servicename[0:3] + ' ' + servicename[4:].title()
    else:
        servicename = servicename.title()
    final_label = (service_label.title()
                   if show_title else '') + ' ' + servicename
    final_label = final_label[:22]
    final_label = final_label.replace('_', ' ')
    final_label = final_label.replace('-', ' ')
    final_label = final_label.replace('This', '').strip()
    return final_label


# Generator function to crawl entire dict and load all dict and list values
def dict_generator(indict, pre=None):
    pre = pre[:] if pre else []
    if isinstance(indict, dict):
        for key, value in indict.items():
            if isinstance(value, dict):
                for d in dict_generator(value, pre + [key]):
                    yield d
            elif isinstance(value, list) or isinstance(value, tuple):
                for v in value:
                    for d in dict_generator(v, pre + [key]):
                        yield d
            else:
                yield pre + [key, value]
    else:
        yield pre + [indict]


# Function to check whether a particular resource mentions another known resource (relationship)
def check_relationship(listitem: str, plist: list, nodes: list,
                       replacements: list, hidden: list) -> list:
    connection_list = []
    resource_name = listitem.strip('${}')
    if resource_name in replacements.keys():
        resource_associated_with = replacements[resource_name]
        resource_name = plist[1] + '.' + plist[2]
    else:
        resource_associated_with = plist[1] + '.' + plist[2]
    # Check if an existing node name appears in parameters of current resource being checked
    matching = [s for s in nodes if s in resource_name]
    # Check if there are any implied connections based on keywords in the param list
    if not matching:
        found_connection = [
            s for s in implied_connections.keys() if s in resource_name
        ]
        if found_connection:
            for n in nodes:
                if n.startswith(implied_connections[found_connection[0]]):
                    matching = [n]
    if (matching):
        reverse = False
        for matched_resource in matching:
            if matched_resource not in hidden and resource_associated_with not in hidden:
                reverse_origin_match = [
                    s for s in reverse_arrow_list if s in resource_name
                ]
                if len(reverse_origin_match) > 0:
                    reverse = True
                    reverse_dest_match = [
                        s for s in reverse_arrow_list
                        if s in resource_associated_with
                    ]
                    if len(reverse_dest_match) > 0:
                        if reverse_arrow_list.index(
                                reverse_dest_match[0]
                        ) < reverse_arrow_list.index(reverse_origin_match[0]):
                            reverse = False
                if reverse:
                    connection_list.append(matched_resource)
                    connection_list.append(resource_associated_with)
                    # Output relationship to console log in reverse order for VPC related nodes
                    click.echo(
                        f'   {matched_resource} --> {resource_associated_with}'
                    )
                elif not 'aws_acm' in resource_associated_with:  # Exception Ignore outgoing connections from ACM certificates and resources mentioned in depends on
                    if listitem in plist:
                        i = plist.index(listitem)
                        if plist[3] == 'depends_on':
                            continue
                    connection_list.append(resource_associated_with)
                    connection_list.append(matched_resource)
                    click.echo(
                        f'   {resource_associated_with} --> {matched_resource}'
                    )
    return connection_list


def output_log(tfdata, variable_list):
    for section in output_sections:
        click.echo(f"\n  {section.title()} list :")
        if tfdata.get("all_" + section):
            for file, valuelist in tfdata["all_" + section].items():
                filepath = Path(file)
                fname = filepath.parent.name + "/" + filepath.name
                for item in valuelist:
                    if isinstance(item, dict):
                        for key in item:
                            click.echo(f"    {fname}: {key}.{next(iter(item[key]))}")
                    else:
                        click.echo(f"    {fname}: {item}")
    if variable_list:
        click.echo("\n  Variable List:")
        for var in variable_list:
            click.echo(f"    var.{var} = {variable_list[var]}")

def getvar(variable_name, all_variables_dict):
    # See if variable exists as an environment variable
    env_var = os.getenv('TF_VAR_' + variable_name)
    if env_var:
        return env_var
    # Check if it exists in all variables dict
    if variable_name in all_variables_dict:
        return all_variables_dict[variable_name]
    else :
        # Check if same variable with different casing exists
        for var in all_variables_dict:
            if var.lower() == variable_name.lower() :
                return all_variables_dict[var]                    
        return 'NOTFOUND'


def replace_variables(vartext, filename, all_variables, quotes=False):
    # Replace Variables found within resource meta data
    if isinstance(filename, list):
        filename = filename[0]
    vartext = str(vartext).strip()
    replaced_vartext = vartext
    var_found_list = re.findall("var\.[A-Za-z0-9_-]+", vartext)
    if var_found_list:
        for varstring in var_found_list:
            varname = varstring.replace('var.', '').lower()
            with suppress(Exception):
                if str(all_variables[varname]) == "":
                    replaced_vartext = replaced_vartext.replace(
                        varstring, '""')
                else:
                    replacement_value = getvar(varname, all_variables)
                    if replacement_value == 'NOTFOUND' :
                        click.echo(click.style(
                            f'\nERROR: No variable value supplied for var.{varname} in {os.path.basename(os.path.dirname(filename))}/{os.path.basename(filename)}', fg='red', bold=True))
                        click.echo('Consider passing a valid Terraform .tfvars variable file with the --varfile parameter or setting a TF_VAR env variable\n')
                        exit()
                    # if isinstance(replacement_value, str) and quotes and not replacement_value.startswith('[') and not replacement_value.isnumeric():
                    #     replacement_value = f'"{replacement_value}"'
                    replaced_vartext = replaced_vartext.replace('${' + varstring + '}', str(replacement_value))
                    replaced_vartext = replaced_vartext.replace(varstring, str(replacement_value))
        return replaced_vartext


def find_resource_references(searchdict: dict, target_resource: str) -> dict:
    final_dict = dict()
    for item in searchdict:
        if target_resource in searchdict[item]:
            final_dict[item] = searchdict[item]
    return final_dict

def list_of_parents(searchdict: dict, target: str) :
    final_list = list()
    for key, value in searchdict.items():
        if isinstance(value, str) :
            if target in value :
                final_list.append(key)
        elif isinstance(value, dict) :
            for subkey in value :
                if target in value[subkey] :
                    final_list.append(key)
    return final_list


def list_of_dictkeys_containing(searchdict: dict, target_keyword: str) -> list:
    final_list = list()
    for item in searchdict:
        if target_keyword in item:
            final_list.append(item)
    return final_list


def replace_locals(vartext, all_locals):
    replaced_vartext = str(vartext).strip()
    var_found_list = re.findall("local\.[A-Za-z0-9_-]+", vartext)
    if var_found_list:
        for varstring in var_found_list:
            varname = varstring.replace('local.', '')
            with suppress(Exception):
                if all_locals.get(varname) == "":
                    replaced_vartext = replaced_vartext.replace(
                        varstring, '""')
                else:
                    replacement_value = all_locals[varname]
                    if isinstance(replacement_value, str):
                        replacement_value = f'{replacement_value}'
                    replaced_vartext = replaced_vartext.replace(
                        varstring, str(replacement_value))
        if replaced_vartext.startswith('{'):
            # Handle cases where local reference found in object/list structure
            return literal_eval(replaced_vartext)
        else:
            while '${' in replaced_vartext:
                replaced_vartext = replaced_vartext.replace('${', '', 1)
                replaced_vartext = ''.join(replaced_vartext.rsplit('}', 1))
    return replaced_vartext


# Cleanup lists with special characters


def fix_lists(eval_string: str):
    eval_string = eval_string.replace('${[]}', '[]')
    if '${' in eval_string:
        eval_string = ''.join(eval_string.rsplit('}', 1))
        eval_string = eval_string.replace('${', '', 1)
    eval_string = eval_string.replace('["[\'', '')
    eval_string = eval_string.replace('\']"]', '')
    # eval_string = eval_string.replace("['", '')
    # eval_string = eval_string.replace("']", '')
    eval_string = eval_string.replace('["[', '[')
    eval_string = eval_string.replace(']"]', ']')
    eval_string = eval_string.replace('[[', '[')
    eval_string = eval_string.replace(',)', ')')
    eval_string = eval_string.replace(',]', ']')
    eval_string = eval_string.replace(']]', ']')
    eval_string = eval_string.replace('[True]', 'True')
    eval_string = eval_string.replace('[False]', 'False')
    return eval_string


# Cleans out special characters
def cleanup(text: str) -> str:
    text = str(text)
    # for ch in ['\\', '`', '*', '{', '}', '[', ']', '(', ')', '>', '!', '$', '\'', '"']:
    for ch in [
            '\\', '`', '*', '{', '}', '(', ')', '>', '!', '$', '\'', '"', '  '
    ]:
        if ch in text:
            text = text.replace(ch, ' ')
    return text.strip()
