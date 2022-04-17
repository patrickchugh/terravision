import ast
import fileinput
import os
import re
import shutil
import tempfile
import click
import git
import hcl2
import requests
import yaml

from git import RemoteProgress
from requests.api import head
from tqdm import tqdm
from contextlib import suppress
from dataclasses import replace
from pathlib import Path
from posixpath import dirname, split
from sys import exit
from urllib.parse import urlparse
from modules.helpers import *
from modules.postfix import Conversion, Evaluate
from sys import exit

# Create Tempdir and Module Cache Directories
all_repos = list()
annotations = dict()
temp_dir = tempfile.TemporaryDirectory(dir=tempfile.gettempdir())
abspath = os.path.abspath(__file__)
dname = os.path.dirname(abspath)
MODULE_DIR = str(Path(Path.home(), '.terravision', 'module_cache'))
if not os.path.exists(MODULE_DIR):
    os.makedirs(MODULE_DIR)

# List of dictionary sections to extract from TF file
extract = [
    'module',
    'output',
    'variable',
    'locals',
    'resource',
    'data'
]

# List of dictionary sections to output in log
output_sections = [
    'locals',
    'module',
    'resource',
    'data'
]


class CloneProgress(RemoteProgress):
    def __init__(self):
        super().__init__()
        self.pbar = tqdm(leave=False)

    def update(self, op_code, cur_count, max_count=None, message=''):
        self.pbar.total = max_count
        self.pbar.n = cur_count
        self.pbar.refresh()


def find_tf_files(source: str, paths=list(), recursive=False) -> list:
    global annotations
    yaml_detected = False
    # If source is a Git address, clone to temp dir
    if ('github' in source or 'bitbucket' in source) and source.startswith('http'):
        source_location = download_files(source, temp_dir.name)
    else:
        # Source is a local folder
        source_location = source.strip()
    if recursive:
        for root, _, files in os.walk(source_location):
            for file in files:
                if file.lower().endswith('.tf') or file.lower().endswith('auto.tfvars'):
                    paths.append(os.path.join(root, file))
    else:
        files = [f for f in os.listdir(source_location)]
        click.echo(f'  Added Source Location: {source}')
        for file in files:
            if file.lower().endswith('.tf') or file.lower().endswith('auto.tfvars'):
                paths.append(os.path.join(source_location, file))
            if file.lower().endswith('architecture.yml') or file.lower().endswith('architecture.yaml') and not yaml_detected:
                full_filepath = Path(source_location).joinpath(file)
                with open(full_filepath, 'r') as file:
                    click.echo(f'  Detected architecture annotation file : {file.name} \n')
                    yaml_detected = True
                    annotations = yaml.safe_load(file)
    if len(paths) == 0:
        click.echo(
            'ERROR: No Terraform .tf files found in current directory or your source location. Use --source parameter to specify location or Github URL of source files')
        exit()
    return paths


def output_log(tfdata, variable_list):
    for section in output_sections:
        click.echo(f'\n  {section.title()} list :')
        if tfdata.get('all_'+section) :
            for file, valuelist in tfdata['all_'+section].items():
                filepath = Path(file)
                fname = filepath.parent.name + '/' + filepath.name
                for item in valuelist:
                    if isinstance(item, dict):
                        for key in item:
                            click.echo(f'    {fname}: {key}.{next(iter(item[key]))}')
                    else:
                        click.echo(f'    {fname}: {item}')
    if variable_list:
        click.echo('\n  Variable List:')
        for var in variable_list:
            click.echo(f'    var.{var} = {variable_list[var]}')


def handle_module(modules_list, tf_file_paths, filename):
    temp_modules_dir = temp_dir.name
    module_source_dict = dict()
    # For every module source location, download the files into a new temporary subdirectory
    for i in modules_list:
        for k in i.keys():
            if isinstance(i[k]['source'], list):
                sourceURL = i[k]['source'][0]
            else:
                sourceURL = i[k]['source']
            if not sourceURL in all_repos:
                all_repos.append(sourceURL)
                # Handle local modules on disk
                if sourceURL.startswith('.') or sourceURL.startswith('\\') :
                    if not str(temp_modules_dir) in filename:
                        current_filepath = os.path.abspath(filename)
                        tf_dir = os.path.dirname(current_filepath)
                        os.chdir(tf_dir)
                        os.chdir(sourceURL)
                        modfolder=str(os.getcwd())
                        tf_file_paths = find_tf_files(os.getcwd(), tf_file_paths)
                        os.chdir(dname)
                else:
                    modfolder = download_files(sourceURL, temp_modules_dir, k)
                    tf_file_paths = find_tf_files(modfolder, tf_file_paths)
    # Create a mapping dict between modules and their source dirs for variable separation
    for i in range(len(modules_list)):
        module_stanza = modules_list[i]
        key = next(iter(module_stanza))  # Get first key
        module_source = module_stanza[key]['source']
        # Convert Source URLs to module cache paths
        if not module_source.startswith('.') and not module_source.startswith('\\'):
            localfolder = module_source.replace('/', '_')
            cache_path = os.path.join(temp_modules_dir, ';'+key+';'+localfolder)
            module_source_dict[key] = {'cache_path' : str(cache_path), 'source_file' : filename}
        else:
            module_source_dict[key] = {'cache_path': module_source, 'source_file': filename}
    return {'tf_file_paths': tf_file_paths, 'module_source_dict' : module_source_dict}


def parse_tf_files(source_list: list, varfile_list: tuple, annotate: str) -> dict:
    global annotations
    ''' Parse all .TF extension files in source folder and subdirectories and returns dict with modules, outputs, variables, locals and resources found '''
    filedict = dict()
    tfdata = dict()
    variable_list = dict()
    module_source_dict = dict()
    cwd = os.getcwd()
    for source in source_list:
        # Get List of Terraform Files to parse
        tf_file_paths = find_tf_files(source)
        if annotate:
            with open(annotate, 'r') as file:
                    click.echo(f'  Will override with architecture annotation file : {file.name} \n')
                    annotations = yaml.safe_load(file)
        click.echo(click.style('Reading Terraforms..', fg='white', bold=True))
        # Parse each TF file encountered in source locations
        for filename in tf_file_paths:
            filepath = Path(filename)
            fname = filepath.parent.name + '/' + filepath.name
            click.echo(f'  Parsing {filename}')
            with click.open_file(filename, 'r') as f:
                with suppress(Exception):
                    filedict[filename] = hcl2.load(f)
                # Handle HCL parsing errors due to unexpected characters
                if not filename in filedict.keys():
                    click.echo(
                        f'   WARNING: Unknown Error reading TF file {filename}. Attempting character cleanup fix..')
                    with tempfile.TemporaryDirectory(dir=temp_dir.name) as tempclean:
                        f_tmp = clean_file(filename, str(tempclean))
                        filedict[filename] = hcl2.load(f_tmp)
                        if not filename in filedict.keys():
                            click.echo(f'   ERROR: Unknown Error reading TF file {filename}. Aborting!')
                            exit()
                # Isolate variables, locals and other sections of interest into tfdata dict
                for section in extract:
                    if section in filedict[filename]:
                        section_name = 'all_' + section
                        if not section_name in tfdata.keys():
                            tfdata[section_name] = {}
                        tfdata[section_name][filename] = filedict[filename][section]
                        click.echo(click.style(
                            f'    Found {len(filedict[filename][section])} {section} stanza(s)', fg='green'))
                        if section == 'module':
                            # Expand source locations to include any newly found sub-module locations
                            module_data = handle_module(filedict[filename]['module'], tf_file_paths, filename)
                            tf_file_paths = module_data['tf_file_paths']
                            # Get list of modules and their sources
                            for mod in module_data['module_source_dict']:
                                module_source_dict[mod] = module_data['module_source_dict'][mod]
                             
                            
    # Auto load any tfvars
    for file in tf_file_paths:
        if 'auto.tfvars' in file:
            varfile_list = varfile_list + (file,)
    # Load in variables from user file into a master list
    if len(varfile_list) == 0 and tfdata.get('all_variable'):
        varfile_list = tfdata['all_variable'].keys()
    vardata = get_variable_values(tfdata.get('all_variable'), varfile_list, tfdata.get('all_module'), module_source_dict)
    tfdata['variable_map'] =  vardata['var_mappings']
    tfdata['variable_list'] = vardata['var_data']
    # Inject parent module variables that are referenced downstream in sub modules
    if tfdata.get('all_module'):
        tfdata['variable_map'] = inject_module_variables(tfdata['all_module'],  tfdata['variable_map'])
    if tfdata.get('all_locals'):
        # Evaluate Local Variables containing functions and TF variables and replace with evaluated values
        tfdata['all_locals'] = extract_locals(tfdata['all_locals'], variable_list, tfdata.get('all_output'))
    # Get metadata from resource attributes
    data = get_metadata(tfdata['all_resource'],  tfdata.get('variable_map'), tfdata.get('all_locals'), tfdata.get('all_output'), tfdata.get('all_module'),module_source_dict)
    tfdata['meta_data'] = data['meta_data']
    tfdata['node_list'] = data['node_list']
    tfdata['hidden'] = data['hide']
    tfdata['annotations'] = annotations
    # Dump out findings after file scans are complete
    output_log(tfdata, variable_list)
    # Check for annotations
    temp_dir.cleanup()
    os.chdir(cwd)
    return tfdata

def inject_module_variables(modules: dict, all_variables: dict):
    for file, module_list in modules.items():
        for module_items in module_list:
            for module, params in module_items.items():
                module_source = params['source']
                for key, value in params.items():
                    if 'var.' in str(value):
                        if isinstance(value, list):
                            for i in range(len(value)):
                                value[i] = replace_variables(value[i], module_source, all_variables['main'], False)
                        else:
                            value = replace_variables(value, module_source, all_variables['main'], False)
                    # Add var value to master list of all variables so it can be used downstream
                    if key != 'source' and key != 'version':  # and key in all_variables.keys():
                        all_variables[module][key] = value
    # Add quotes for raw strings to aid postfix evaluation
    for module in all_variables:
        for variable in all_variables[module]:
            value = all_variables[module][variable]
            if isinstance(value, str) and '(' not in value and '[' not in value and not value.startswith('"'):
                all_variables[module][variable] = f'"{value}"'

    return all_variables

def resolve_dynamic_values(value: str, locallist, varlist, all_outputs, filename, mod) -> str:
    # Determine which module's variables we should use
    self_reference = False
    while 'var.' in value or 'local.' in value or 'module.' in value or 'data.' in value:
        oldvalue = value
        if self_reference:
            break
        var_found_list = re.findall("var\.[A-Za-z0-9_\-]+", value)
        data_found_list = re.findall("data\.[A-Za-z0-9_\-\.\[\]]+", value)
        varobject_found_list = re.findall("var\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+", value)
        local_found_list = re.findall("local\.[A-Za-z0-9_\-]+", value)
        modulevar_found_list = re.findall("module\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+", value)
        for d in data_found_list:
            value = value.replace(d, '""')
        for module in modulevar_found_list:
            cleantext = fix_lists(module)
            splitlist = cleantext.split('.')
            outputname = find_between(cleantext, splitlist[1] + '.', ' ')
            oldvalue = value
            for ofile in all_outputs.keys():
                for i in all_outputs[ofile]:
                    if outputname in i.keys():
                        value = value.replace(module, i[outputname]['value'])
            if value == oldvalue:
                value = value.replace(module, 'UNKNOWN')
        for varitem in var_found_list:
            lookup = varitem.split('var.')[1].lower()
            if lookup in varlist.keys() and 'var.' + lookup not in str(varlist[lookup]):
                # Possible object type var encountered
                obj = ""
                for item in varobject_found_list:
                    if lookup in item:
                        obj = varlist[lookup]
                        varitem = item
                #click.echo(f'    var.{lookup}')
                if value.count(lookup) < 2 and obj != '' and isinstance(obj, dict):
                    key = varitem.split('.')[2]
                    keyvalue = obj[key]
                    if isinstance(keyvalue, str) and not keyvalue.startswith('[') and not keyvalue.startswith('{'):
                        keyvalue = f'"{keyvalue}"'
                    value = value.replace(varitem, str(keyvalue))
                elif value.count(lookup) < 2 and obj == '':
                    replacement_value = str(varlist.get(lookup))
                    if isinstance(replacement_value, str) and '"' not in replacement_value and not replacement_value.startswith('['):
                        replacement_value = f'"{replacement_value}"'
                    value = value.replace(varitem, replacement_value)
                else:
                    value = value.replace(varitem+' ', str(varlist[lookup])+' ')
                    value = value.replace(varitem+',', str(varlist[lookup])+',')
                    value = value.replace(varitem+')', str(varlist[lookup])+')')
                    value = value.replace(varitem+']', str(varlist[lookup])+']')
            elif varlist.get(lookup):
                # Self referencing variable (duplicate across modules)
                value = value.replace(varitem, str(varlist.get(lookup)))
                self_reference = True
                break
            else:
                click.echo(click.style(
                    f'\nERROR: No variable value supplied for {varitem} but it is referenced in {filename} ', fg='white', bold=True))
                click.echo(
                    'Consider passing a valid Terraform .tfvars variable file with the --varfile parameter\n')
                exit()
        for localitem in local_found_list:
            lookup = localitem.split('local.')[1]
            if locallist:
                if lookup in locallist.keys():
                    replacement_value = str(locallist.get(lookup))
                    value = value.replace(localitem, replacement_value)
                else:
                    value = value.replace(localitem,  'None')
                    click.echo(f'    WARNING: Cannot resolve {localitem}, assigning empty value')
            else :
                value = value.replace(localitem,  'None')
                click.echo(f'    WARNING: Cannot resolve {localitem}, assigning empty value')
        if oldvalue == value:
            click.echo(f'    WARNING: Cannot resolve {lookup}')
            break
    return value


def extract_locals(locallist, varlist, all_outputs):
    click.echo('\n  Parsing locals...')
    final_locals = dict()
    module_locals = dict()
    # Remove array layer of locals dict structure and copy over to final_locals dict first
    for file, localvarlist in locallist.items():
        final_locals[file] = localvarlist[0]
        if ';' in file :
            modname = file.split(';')[1]
        else :
            modname = 'main'
        if module_locals.get(modname) :
            module_locals[modname] = {**module_locals[modname], **localvarlist[0]}
        else :
            module_locals[modname] = localvarlist[0]
    return module_locals


def handle_readme_source(resp) -> str:
    readme = resp.json()['root']['readme']
    githubURL = 'ssh://git@' + find_between(readme, '(https://', ')')
    found = re.findall('\.........\.net', githubURL)
    for site in found:
        githubURL = githubURL.replace(site, '-ssh' + site)
    githubURL = githubURL.replace('/projects/', ':7999/')
    githubURL = githubURL.replace('/repos/', '/')
    startindex = githubURL.index('/browse?')
    githubURL = githubURL[0:startindex] + '.git'
    return githubURL

# # TODO: Break download_files down into a smaller function
# def download_files(sourceURL: str, tempdir: str, module=''):
#     click.echo(click.style('Loading Sources..', fg='white', bold=True))
#     subfolder = ''
#     gitaddress = ''
#     reponame = sourceURL.replace('/', '_')
#     module_cache_path = os.path.join(MODULE_DIR, reponame)
#     # Identify source repo and construct final git clone URL
#     click.echo(f'  Downloading External Module: {sourceURL}')
#     if sourceURL.startswith('github.com') or sourceURL.startswith('https://github.com/'):
#         if sourceURL.count('//') > 1:
#             subfolder_array = sourceURL.split('//')
#             subfolder = subfolder_array[2].split('?')[0]
#             gitaddress = subfolder_array[0] + '//' + subfolder_array[1]
#         githubURL = gitaddress if gitaddress else sourceURL
#         sourceURL = gitaddress if gitaddress else sourceURL
#         r = requests.get(url(sourceURL))
#     elif sourceURL.startswith('git::ssh://') or sourceURL.startswith('git@github.com') or 'git::' in sourceURL:
#         if 'ssh://' in sourceURL:
#             split_array = sourceURL.split('git::ssh://')
#         elif 'git::http' in sourceURL:
#             split_array = sourceURL.split('git::')
#         else:
#             split_array = sourceURL.split('git::')
#         gitaddress = split_array[-1]
#         gitaddress = gitaddress.replace('git@github.com/', 'git@github.com:')
#         if '//' in gitaddress and not gitaddress.startswith('https://'):
#             subfolder_array = gitaddress.split('//')
#             subfolder = subfolder_array[1].split('?')[0]
#             gitaddress = subfolder_array[0]
#         githubURL = gitaddress
#     else:
#         # URL is a Terraform Registry Module linked via git
#         gitaddress = sourceURL
#         headers = ''
#         if check_for_domain(sourceURL):
#             domain = urlparse('https://' + sourceURL).netloc
#             registrypath = sourceURL.split(domain)
#             gitaddress = registrypath[1]
#             domain = 'https://' + domain + '/api/registry/v1/modules/'
#             click.echo(f'    Assuming Terraform Enterprise API Server URL: {domain}')
#             if not 'TFE_TOKEN' in os.environ:
#                 click.echo(click.style(
#                     '\nERROR: No TFE_TOKEN environment variable set. Unable to authorise with Terraform Enterprise Server', fg='red', bold=True))
#                 exit()
#             else:
#                 headers = {'Authorization': 'bearer ' + os.environ['TFE_TOKEN']}
#         else:
#             domain = 'https://registry.terraform.io/v1/modules/'
#         if sourceURL.count('//') >= 1:
#             # Clone only the Subfolder specified
#             subfolder_array = sourceURL.split('//')
#             subfolder = subfolder_array[1].split('?')[0]
#             gitaddress = subfolder_array[0]
#         r = requests.get(domain + gitaddress, headers=headers)
#         try:
#             githubURL = r.json()['source']
#         except:
#             click.echo(click.style(
#                 '\nERROR: Received invalid response from Terraform Enterprise server. Check authorisation token, server address and network settings', fg='red', bold=True))
#             exit()
#         if githubURL == '':
#             githubURL = handle_readme_source(r)
#         click.echo(click.style(f'    Cloning from Terraform registry source: {githubURL}', fg='green'))
#     # Now do a git clone or skip if we already have seen this module before
#     if os.path.exists(os.path.join(MODULE_DIR, reponame)):
#         click.echo(f'  Skipping download of module {reponame}, found existing folder in module cache')
#         return os.path.join(module_cache_path, subfolder)
#     else:
#         os.makedirs(module_cache_path)
#         try:
#             git.Repo.clone_from(url(githubURL), str(module_cache_path), progress=CloneProgress())
#         except:
#             click.echo(click.style(
#                 f'\nERROR: Unable to call Git to clone repository! Ensure git is configured properly and the URL {githubURL} is reachable.', fg='red', bold=True))
#             os.rmdir(module_cache_path)
#             exit()
#     if module:
#         temp_module_path = os.path.join(tempdir, ';'+module+';'+reponame)
#         shutil.copytree(module_cache_path, temp_module_path)
#         return os.path.join(module_cache_path, subfolder)
#     return os.path.join(tempdir, subfolder)

def get_clone_url(sourceURL: str) :
    # Handle Case where full git url is given
    if sourceURL.startswith('github.com') or sourceURL.startswith('https://github.com/'):
        # Handle subfolder of git repo
        if sourceURL.count('//') > 1:
            subfolder_array = sourceURL.split('//')
            subfolder = subfolder_array[2].split('?')[0]
            gitaddress = subfolder_array[0] + '//' + subfolder_array[1]
        githubURL = gitaddress if gitaddress else sourceURL
        # sourceURL = gitaddress if gitaddress else sourceURL
        #r = requests.get(sourceURL)
    # Handle case where ssh git URL is given
    elif sourceURL.startswith('git::ssh://') or sourceURL.startswith('git@github.com') or 'git::' in sourceURL:
        if 'ssh://' in sourceURL:
            split_array = sourceURL.split('git::ssh://')
        elif 'git::http' in sourceURL:
            split_array = sourceURL.split('git::')
        else:
            split_array = sourceURL.split('git::')
        gitaddress = split_array[-1]
        gitaddress = gitaddress.replace('git@github.com/', 'git@github.com:')
        if '//' in gitaddress and not gitaddress.startswith('https://'):
            subfolder_array = gitaddress.split('//')
            subfolder = subfolder_array[1].split('?')[0]
            gitaddress = subfolder_array[0]
        githubURL = gitaddress
    else:
        # URL is a Terraform Registry Module linked via git
        gitaddress = sourceURL
        headers = ''
        if check_for_domain(sourceURL):
            domain = urlparse('https://' + sourceURL).netloc
            registrypath = sourceURL.split(domain)
            gitaddress = registrypath[1]
            domain = 'https://' + domain + '/api/registry/v1/modules/'
            click.echo(f'    Assuming Terraform Enterprise API Server URL: {domain}')
            if not 'TFE_TOKEN' in os.environ:
                click.echo(click.style(
                    '\nERROR: No TFE_TOKEN environment variable set. Unable to authorise with Terraform Enterprise Server', fg='red', bold=True))
                exit()
            else:
                headers = {'Authorization': 'bearer ' + os.environ['TFE_TOKEN']}
        else:
            domain = 'https://registry.terraform.io/v1/modules/'
        if sourceURL.count('//') >= 1:
            # Clone only the Subfolder specified
            subfolder_array = sourceURL.split('//')
            subfolder = subfolder_array[1].split('?')[0]
            gitaddress = subfolder_array[0]
        r = requests.get(domain + gitaddress, headers=headers)
        try:
            githubURL = r.json()['source']
        except:
            click.echo(click.style(
                '\nERROR: Received invalid response from Terraform Enterprise server. Check authorisation token, server address and network settings', fg='red', bold=True))
            exit()
        if githubURL == '':
            githubURL = handle_readme_source(r)
    return githubURL


def download_files(sourceURL: str, tempdir: str, module=''):
    click.echo(click.style('Loading Sources..', fg='white', bold=True))
    subfolder = ''
    reponame = sourceURL.replace('/', '_')
    module_cache_path = os.path.join(MODULE_DIR, reponame)
    # Identify source repo and construct final git clone URL
    click.echo(f'  Downloading External Module: {sourceURL}')
    githubURL = get_clone_url(sourceURL)
    click.echo(click.style(f'    Cloning from Terraform registry source: {githubURL}', fg='green'))
    # Now do a git clone or skip if we already have seen this module before
    if os.path.exists(module_cache_path):
        click.echo(f'  Skipping download of module {reponame}, found existing folder in module cache')
        if module:
            temp_module_path = os.path.join(tempdir, ';'+module+';'+reponame)
            shutil.copytree(module_cache_path, temp_module_path)
            return os.path.join(temp_module_path, subfolder)
        else :
            return os.path.join(module_cache_path, subfolder)
    else:
        os.makedirs(module_cache_path)
        try:
            clonepath = git.Repo.clone_from(githubURL, str(module_cache_path), progress=CloneProgress())
        except:
            click.echo(click.style(
                f'\nERROR: Unable to call Git to clone repository! Ensure git is configured properly and the URL {githubURL} is reachable.', fg='red', bold=True))
            os.rmdir(module_cache_path)
            exit()
    return os.path.join(module_cache_path, subfolder)


def clean_file(filename: str, tempdir: str):
    filepath = str(Path(tempdir, 'cleaning.tmp'))
    f_tmp = click.open_file(filepath, 'w')
    with fileinput.FileInput(filename, inplace=False,) as file:
        for line in file:
            if line.strip().startswith('#'):
                continue
            if '", "' in line or ':' in line or '*' in line or '?' in line or '[' in line or '("' in line or '==' in line or '?' in line or ']' in line or ':' in line:
                # if '", "' in line or ':' in line or '*' in line or '?' in line or '[' in line or '("' in line or '==' in line or '?' in line or '${' in line or ']' in line:
                if 'aws_' in line and not 'resource' in line:
                    array = line.split('=')
                    if len(array) > 1:
                        badstring = array[1]
                    else:
                        badstring = line
                    cleaned_string = re.sub(
                        '[^0-9a-zA-Z._]+', ' ', badstring)
                    line = array[0] + ' = "' + \
                        cleaned_string + '"'
                else:
                    line = f'# {line}' + '\r'
            f_tmp.write(line)
    f_tmp = click.open_file(filepath, 'r')
    return f_tmp


def replace_data_statements(statement: str):
    data_found_list = re.findall("data\.[A-Za-z0-9_\-\.]+", statement)
    for d in data_found_list:
        resource = d.split('data.')[1]
        if '"' in statement:
            statement = statement.replace(d, resource)
        else:
            statement = statement.replace(d, f'"{resource}"')
    return statement


def process_conditional_metadata(metadata: dict, mod_locals, all_variables, all_outputs, filename, mod):

    def determine_statement(eval_string: str):
        if 'for' in eval_string and 'in' in eval_string:
            # we have a for loop so deal with that part first
            # TODO: Implement for loop handling for real, for now just null it out
            eval_string = find_between(eval_string, '[for', ':', '[', True, eval_string.count('['))
            eval_string = find_between(eval_string, ':', ']', '', True,  eval_string.count(']'))
        if 'module.' in eval_string:
            outvalue = ''
            splitlist = eval_string.split('.')
            outputname = find_between(eval_string, splitlist[1] + '.', ' ')
            for file in all_outputs.keys():
                for i in all_outputs[file]:
                    if outputname in i.keys():
                        outvalue = i[outputname]['value']
                        if '*.id' in outvalue:
                            resource_name = fix_lists(outvalue.split('.*')[0])
                            outvalue = metadata[resource_name]['count']
                            outvalue = determine_statement(outvalue)
                            break
            stringarray = eval_string.split('.')
            modulevar = cleanup('module' + '.' + stringarray[1] + '.' + stringarray[2]).strip()
            eval_string = eval_string.replace(modulevar, outvalue)
        eval_string = resolve_dynamic_values(eval_string, mod_locals, all_variables, all_outputs, filename, mod)
        return eval_string

    for resource, attr_list in metadata.items():
        if 'count' in attr_list.keys() and not isinstance(attr_list['count'], int) and not resource.startswith('null_resource'):
            eval_string = str(attr_list['count'])
            eval_string = determine_statement(eval_string)
            exp = handle_conditionals(eval_string, mod_locals, all_variables, filename)
            filepath = Path(filename)
            fname = filepath.parent.name + '/' + filepath.name
            #fname = filename.split('_')[-2] + filename.split('_')[-1]
            if not 'ERROR!' in exp:
                obj = Conversion(len(exp))
                pf = obj.infixToPostfix(exp)
                if not pf == 'ERROR!':
                    obj = Evaluate(len(pf))
                    eval_value = obj.evaluatePostfix(pf)
                    if eval_value == '' or eval_value == ' ':
                        eval_value = 0
                    fname2 = fname.replace(';','|')
                    click.echo(f'    {fname2} : {resource} count = {eval_value} ({exp})')
                    attr_list['count'] = int(eval_value)
                else:
                    click.echo(f'    ERROR: {fname} : {resource} count = 0 (Error in evaluation of value {exp})')
            else:
                click.echo(f'    ERROR: {fname} : {resource} count = 0 (Error in calling function {exp}))')
        if 'for_each' in attr_list:
            attr_list['for_each'] = determine_statement(attr_list['for_each'])
    return metadata


def get_metadata(all_resources: dict, variable_list: dict, all_locals: dict, all_outputs: dict, all_modules:dict, module_map: dict) -> set:
    ''' 
    Extract resource attributes from resources by looping through each resource in each file. 
    Returns a set with a node_list of unique resources, resource attributes (metadata) and hidden (zero count) nodes
    '''
    node_list = []
    meta_data = dict()
    click.echo(f'\n  Conditional Resource List:')
    for filename, resource_list in all_resources.items():
        if ';' in filename:
            # We have a module file being processed
            modarr = filename.split(';')
            mod = modarr[1]
        else :
            mod = 'main'
        for item in resource_list:
            for k in item.keys():
                resource_type = k
                for i in item[k]:
                    resource_name = i
                    # Check if Cloudwatch is present in policies and create node for Cloudwatch service if found
                    if resource_type == 'aws_iam_policy':
                        if 'logs:' in item[resource_type][resource_name]['policy'][0]:
                            if not 'aws_cloudwatch_log_group.logs' in node_list:
                                node_list.append('aws_cloudwatch_log_group.logs')
                            meta_data['aws_cloudwatch_log_group.logs'] = item[resource_type][resource_name]
                # click.echo(f'    {resource_type}.{resource_name}')
                node_list.append(f'{resource_type}.{resource_name}')
                # Check if any variables are present and replace with values if known
                attribute_values = item[k][i]
                for attribute, attribute_value in attribute_values.items():
                    if isinstance(attribute_value, list):
                        for index, listitem in enumerate(attribute_value):
                            if 'var.' in str(listitem):
                                attribute_value[index] = replace_variables(listitem, filename, variable_list[mod])
                            if 'local.' in str(listitem):
                                attribute_value[index] = replace_locals(str(listitem), all_locals[mod])
                    if isinstance(attribute_value, str):
                        if 'var.' in attribute_value:
                            attribute_values[attribute] = replace_variables(attribute_value, filename, variable_list[mod])
                        if 'local.' in attribute_value:
                            attribute_values[attribute] = replace_locals(attribute_value, all_locals[mod])
                meta_data[f'{resource_type}.{resource_name}'] = attribute_values    
        meta_data = process_conditional_metadata(meta_data, all_locals.get(mod) if all_locals else None, variable_list.get(mod) if variable_list else None, all_outputs, filename, mod)
    
    # Handle CF Special meta data
    cf_data = [s for s in meta_data.keys() if 'aws_cloudfront' in s]
    if cf_data:
        for cf_resource in cf_data:
            if 'origin' in meta_data[cf_resource]:
                for origin_source in meta_data[cf_resource]['origin']:
                    if isinstance(origin_source, str) and origin_source.startswith('{'):
                        origin_source = literal_eval(origin_source)
                    origin_domain = cleanup(origin_source.get('domain_name')).strip()
                    if origin_domain:
                        meta_data[cf_resource]['origin'] = handle_cloudfront_domains(
                            str(origin_source), origin_domain, meta_data)
    to_hide = [key for key, attr_list in meta_data.items() if str(attr_list.get('count')) == '0']
    return {'meta_data': meta_data, 'node_list': node_list, 'hide': to_hide}


def handle_cloudfront_domains(origin_string: str, domain: str, mdata: dict) -> str:
    for key, value in mdata.items():
        for k, v in value.items():
            if domain in str(v) and not domain.startswith('aws_'):
                o = origin_string.replace(domain, key)
                return origin_string.replace(domain, key)
    return origin_string


def get_variable_values(all_variables: dict, varfile_list: list, all_modules: dict, module_sources: dict) -> dict:
    ''' Returns a list of all variables merged from local .tfvar defaults, supplied varfiles and module values'''
    click.echo('Processing Variables..')
    if not all_variables:
        all_variables = dict()
    var_data = dict()
    var_mappings = dict()
    # Load default values from all existing files in source locations
    for var_source_file, var_list in all_variables.items():
        var_source_dir = str(Path(var_source_file).parent)
        for item in var_list:
            for k in item.keys():
                var_name = k
                for var_attr in item[k]:
                    # Populate dict with default values first
                    if var_attr == 'default' : #and not var_name in variable_values.keys():
                        if item[k][var_attr] == "":
                            var_value = ''
                        else:
                            var_value = item[k][var_attr]
                        var_data[var_name] = var_value
                        # Also update var mapping dict with modules and matching variables
                        matching = [m for m in module_sources if module_sources[m]['cache_path'][1:-1] in str(var_source_file)] # omit first char of module source in case it is a .
                        if not matching:
                            if not var_mappings.get('main'):
                                var_mappings['main'] = {}
                                var_mappings['main'] = {'source_dir': var_source_dir}
                            var_mappings['main'][var_name] = var_value
                        for mod in matching:
                            if not var_mappings.get(mod) :
                                var_mappings[mod] = {}
                                var_mappings[mod]['source_dir'] = var_source_dir
                            var_mappings[mod][var_name] = var_value
    if all_modules:                       
        # Insert module parameters as variable names
        for file, modulelist in all_modules.items():
            for module in modulelist:
                for mod, params in module.items():
                    for variable in params:
                        var_data[variable] = params[variable]
                        if not var_mappings.get(mod) :
                            var_mappings[mod] ={}
                        var_mappings[mod][variable] = params[variable]
    if varfile_list:
        # Over-write defaults with passed varfile specified values
        for varfile in varfile_list:
            # Open supplied varfile for reading
            with click.open_file(varfile, 'r') as f:
                variable_values = hcl2.load(f)
            for uservar in variable_values:
                var_data[uservar.lower()] = variable_values[uservar]
                if not var_mappings.get('main') :
                    var_mappings['main'] = {}
                var_mappings['main'][uservar.lower()] = variable_values[uservar]

    return {'var_data': var_data, 'var_mappings':var_mappings}