import os
import sys
import time
import json
import yaml
import tarfile
import argparse
import requests
import logging
import coloredlogs

from ibm_cloud_sdk_core import *
from ibm_code_engine_sdk.code_engine_v2 import *
from ibm_cloud_sdk_core.authenticators import IAMAuthenticator
from ibm_platform_services import ResourceManagerV2

try:
    from http.client import HTTPConnection
except ImportError:
    from httplib import HTTPConnection

LOGGER = None
LOG_LEVEL = None
AUTHENTICATOR = None
CODE_ENGINE_SERVICE = None
CODE_ENGINE_PROJECT_NAME = None
REGISTRY_SERVER = None
CONFIG_MAP_NAME = None
SECRET_MAP_NAME = None
REGISTRY_SECRET_NAME = None
BUILD_NAME = None
IMAGE_PATH = None
BUILD_RUN_NAME = None
APPLICATION_NAME = None

#test

def log_config():
  global LOGGER
  LOGGER = logging.getLogger('__name__')
  log_formatter = '%(asctime)s::%(funcName)s::%(levelname)s:: %(message)s'
  coloredlogs.install(level=LOG_LEVEL, logger=LOGGER, fmt=log_formatter)


def cli_args_config():
  parser = argparse.ArgumentParser(
      description='Code Engine Deployment for API Assistant',
  )

  parser.add_argument(
      "ibm_cloud_token",
      type=str,
      help="IBM Cloud IAM Token"
  )

  parser.add_argument(
      "--log_level",
      required=False,
      type=str,
      choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
      default="INFO",
      help="Required log level"
  )

  parser.add_argument(
      "resource_group_name",
      type=str,
      help="IBM Cloud Resource Group name"
  )

  parser.add_argument(
      "--ibm_iam_url",
      type=str,
      required=False,
      default=DEFAULT_IAM_URL,
      help="IBM Cloud IAM URL"
  )

  parser.add_argument(
      "ce_project_name",
      type=str,
      help="IBM Code Engine Project name"
  )

  parser.add_argument(
      "icr_namespace_name",
      type=str,
      help="ICR Namespace name for the image"
  )

  parser.add_argument(
      "--icr_token",
      type=str,
      required=False,
      default=None,
      help="IBM Cloud Registry Token"
  )

  return parser.parse_args()


def authenticator_generator(cli_args):
  global AUTHENTICATOR
  AUTHENTICATOR = IAMAuthenticator(
      cli_args.ibm_cloud_token, url=IBM_IAM_URL)


def resource_group_id_provider(resource_group_name):
  resource_manager_service = ResourceManagerV2(authenticator=AUTHENTICATOR)
  resource_group_list = resource_manager_service.list_resource_groups(
  ).get_result().get('resources')
  for resource_group in resource_group_list:
    if resource_group['name'] == resource_group_name:
      LOGGER.info(f"Resource Group ID: {YELLOW}{resource_group['id']}{RESET}")
      return resource_group['id']
  raise Exception(f'{RED}Resource group not found{RESET}')


def code_engine_service_generator():
  global CODE_ENGINE_SERVICE

  CODE_ENGINE_SERVICE = CodeEngineV2(
      authenticator=AUTHENTICATOR, version=VERSION)

  if CODE_ENGINE_SERVICE is None:
    raise Exception('{RED}Code Engine Service not initialized{RESET}')

  CODE_ENGINE_SERVICE.set_service_url(CODE_ENGINE_URL)


def registry_secret_provider(cli_args, project_id):
  if cli_args.icr_token is not None:
    icr_token = cli_args.icr_token
  else:
    icr_token = cli_args.ibm_cloud_token

  registry_secret_data = SecretDataRegistrySecretData(
      username='iamapikey', password=icr_token, server='icr.io')

  try:
    response = CODE_ENGINE_SERVICE.get_secret(
        project_id=project_id,
        name=REGISTRY_SECRET_NAME,
    ).get_result()

    LOGGER.debug(f'Registry with name {YELLOW}{REGISTRY_SECRET_NAME}{RESET} exists, recreating the registry secret.')

    CODE_ENGINE_SERVICE.delete_secret(
        project_id=project_id,
        name=REGISTRY_SECRET_NAME,
    ).get_result()

    response = CODE_ENGINE_SERVICE.create_secret(
        project_id=project_id,
        format='registry',
        name=REGISTRY_SECRET_NAME,
        data=registry_secret_data,
    )
  except ApiException:
      response = CODE_ENGINE_SERVICE.create_secret(
          project_id=project_id,
          format='registry',
          name=REGISTRY_SECRET_NAME,
          data=registry_secret_data,
      )

  secret = response.get_result()

  response = CODE_ENGINE_SERVICE.get_secret(
      project_id=project_id,
      name=REGISTRY_SECRET_NAME,
  )
  secret = response.get_result()
  del secret['data']['password']
  LOGGER.debug(f"Registry Secret:\n{json.dumps(secret, indent=2)}")
  return secret


def project_exists(pager):
  while pager.has_next():
      next_page = pager.get_next()
      if next_page is not None:
        for current_project in next_page:
          if current_project['name'] == CODE_ENGINE_PROJECT_NAME:
              LOGGER.info(f"Project exists, project ID: {YELLOW}{current_project['id']}{RESET}")
              return current_project['id']
  LOGGER.warning(f'{RED}Project does not exist{RESET}, will try to create a new project with name {YELLOW}{CODE_ENGINE_PROJECT_NAME}{RESET}')
  return False


def project_provider(cli_args):
  project = None
  resource_group_id = resource_group_id_provider(cli_args.resource_group_name)

  pager = ProjectsPager(
      client=CODE_ENGINE_SERVICE,
      limit=100,
  )

  project_id = project_exists(pager)

  if not project_id:
      response = CODE_ENGINE_SERVICE.create_project(
          name=CODE_ENGINE_PROJECT_NAME,
          resource_group_id=resource_group_id
      )
      project = response.get_result()
  else:
    project = CODE_ENGINE_SERVICE.get_project(
        id=project_id
    ).get_result()

  project_status = project['status']

  while project_status in ['creating', 'pending']:
    time.sleep(10)
    project_status = CODE_ENGINE_SERVICE.get_project(
        id=project['id']
    ).get_result()['status']
    LOGGER.debug(f'Project {YELLOW}{CODE_ENGINE_PROJECT_NAME}{RESET} Status: {BLUE}{str(project_status).upper()}{RESET}')

  LOGGER.info(f'Project {YELLOW}{CODE_ENGINE_PROJECT_NAME}{RESET} Status: {BLUE}{str(project_status).upper()}{RESET}')

  LOGGER.debug(f'Project {YELLOW}{CODE_ENGINE_PROJECT_NAME}{RESET} Config:\n{json.dumps(project, indent=2)}')
  return project


def build_generator(project_id, registry_secret_name):
  try:
    response = CODE_ENGINE_SERVICE.get_build(
        project_id=project_id,
        name=BUILD_NAME,
    ).get_result()

    CODE_ENGINE_SERVICE.delete_build(
        project_id=project_id,
        name=BUILD_NAME,
    )

    response = CODE_ENGINE_SERVICE.create_build(
        project_id=project_id,
        name=BUILD_NAME,
        output_image=IMAGE_PATH,
        output_secret=registry_secret_name,
        strategy_type='buildpacks',
        source_type='local',
        strategy_size='small',
    )
  except ApiException:
    response = CODE_ENGINE_SERVICE.create_build(
        project_id=project_id,
        name=BUILD_NAME,
        output_image=IMAGE_PATH,
        output_secret=registry_secret_name,
        strategy_type='buildpacks',
        source_type='local',
        strategy_size='small',
    )

  build = response.get_result()

  while build['status'] != 'ready':
    response = CODE_ENGINE_SERVICE.get_build(
        project_id=project_id,
        name=BUILD_NAME,
    )

    build = response.get_result()

    LOGGER.info(f"Build {YELLOW}{BUILD_NAME}{RESET} Status: {BLUE}{str(build['status']).upper()}{RESET}")
    time.sleep(10)

  LOGGER.debug(f'Build {YELLOW}{BUILD_NAME}{RESET} Config:\n{json.dumps(build, indent=2)}')


def source_tar_generator():
  try:
    file_path = os.path.join(FILE_DIR, SOURCE_FILE_NAME)

    with tarfile.open(file_path, 'w:gz') as tar:
      tar.add(BUILD_SPEC_FILE_NAME)
      tar.add('requirements.txt')
      tar.add('.ceignore')
      tar.add(SOURCE_CODE_PATH)
  except Exception as e:
    raise Exception(f'{RED}Error creating source archive{RESET}')

  LOGGER.info(f'Archive with required source files created successfully.')
  LOGGER.info(f'Archive File: {YELLOW}{file_path}{RESET}')
  return file_path


def build_run_generator(project_id):
  token = AUTHENTICATOR.token_manager.get_token()
  source_file = source_tar_generator()
  url = f"{CODE_ENGINE_URL}/projects/{project_id}/build_runs"
  files = {
      'json': json.dumps({
          "name": BUILD_RUN_NAME,
          "build_name": BUILD_NAME,
          "project_id": project_id
      }),
      'source': (SOURCE_FILE_NAME, open(source_file, 'rb'), 'application/octet-stream')
  }

  headers = {'authorization': f'Bearer {token}', 'accept': 'application/json'}
  response = requests.post(url, headers=headers, files=files)
  build_run = response.json()
  LOGGER.debug(f'Build Run Config:\n{json.dumps(build_run, indent=2)}')

  while build_run['status'] in ['running', 'pending']:

      response = CODE_ENGINE_SERVICE.get_build_run(
          project_id=project_id,
          name=BUILD_RUN_NAME,
      )

      build_run = response.get_result()
      LOGGER.info(f"Build Run {YELLOW}{BUILD_RUN_NAME}{RESET} Status: {BLUE}{str(build_run['status']).upper()}{RESET}")

      time.sleep(15)


def get_config_map_data():
  config_map_data = {}
  secret_map_data = {}

  file_path = os.path.join(FILE_DIR, CM_FILE_NAME)

  with open(file_path, 'r') as file:
    for line in file:
      line = line.strip()
      if "=" in line:
        key, value = line.split('=')
        if key.find('pswd') or key.find('password'):
          secret_map_data[key] = value
        else:
          config_map_data[key] = value

  return config_map_data, secret_map_data


def env_var_provider(project_id):
  config_map_data, secret_map_data = get_config_map_data()

  try:
    response = CODE_ENGINE_SERVICE.create_config_map(
        project_id=project_id,
        name=CONFIG_MAP_NAME,
        data=config_map_data
    )
  except ApiException:
    CODE_ENGINE_SERVICE.delete_config_map(
        project_id=project_id,
        name=CONFIG_MAP_NAME,
    ).get_result()

    response = CODE_ENGINE_SERVICE.create_config_map(
        project_id=project_id,
        name=CONFIG_MAP_NAME,
        data=config_map_data
    )

  try:
    response = CODE_ENGINE_SERVICE.create_secret(
        project_id=project_id,
        name=SECRET_MAP_NAME,
        format='generic',
        data=secret_map_data
    )
  except ApiException:
    CODE_ENGINE_SERVICE.delete_secret(
        project_id=project_id,
        name=SECRET_MAP_NAME,
    ).get_result()

    response = CODE_ENGINE_SERVICE.create_secret(
        project_id=project_id,
        name=SECRET_MAP_NAME,
        format='generic',
        data=secret_map_data
    ).get_result()

  env_data = [
      {
          'name': CONFIG_MAP_NAME,
          'type': 'config_map_full_reference',
          'reference': CONFIG_MAP_NAME
      },
      {
          'name': SECRET_MAP_NAME,
          'type': 'secret_full_reference',
          'reference': SECRET_MAP_NAME
      }
  ]

  LOGGER.debug(f'Environment Variables Mapping:\n{json.dumps(env_data, indent=2)}')
  return env_data


def application_generator(project_id):
  env_vars = env_var_provider(project_id=project_id)
  try:
    app = CODE_ENGINE_SERVICE.get_app(
        project_id=project_id,
        name=APPLICATION_NAME
    ).get_result()

    CODE_ENGINE_SERVICE.delete_app(
        project_id=project_id,
        name=APPLICATION_NAME
    )
    response = CODE_ENGINE_SERVICE.create_app(
        project_id=project_id,
        image_reference=IMAGE_PATH,
        image_secret=REGISTRY_SECRET_NAME,
        name=APPLICATION_NAME,
        run_env_variables=env_vars
    )
  except ApiException:
    response = CODE_ENGINE_SERVICE.create_app(
        project_id=project_id,
        image_reference=IMAGE_PATH,
        image_secret=REGISTRY_SECRET_NAME,
        name=APPLICATION_NAME,
        run_env_variables=env_vars
    )

  app = response.get_result()
  LOGGER.debug(f'App Data:\n{json.dumps(app, indent=2)}')


def application_url_provider(project_id):
  app = None

  while app is None or app['status'] not in ['pending', 'failed', 'ready']:
    app = CODE_ENGINE_SERVICE.get_app(
        project_id=project_id,
        name=APPLICATION_NAME
    ).get_result()

    LOGGER.info(f"App {YELLOW}{APPLICATION_NAME}{RESET} Status: {BLUE}{str(app['status']).upper()}{RESET}")
    time.sleep(10)

  if app['status'] == 'failed':
    LOGGER.error(
        f"{RED}App {YELLOW}{APPLICATION_NAME} {RED}failed to deploy, please check logs for more details.{RESET}")
    LOGGER.error(f"App {YELLOW}{APPLICATION_NAME}{RESET} Data:\n{json.dumps(app, indent=2)}")
    raise Exception(f'{RED}App {YELLOW}{APPLICATION_NAME}{RESET} failed to deploy{RESET}')
  elif app['status'] == 'ready':
    LOGGER.info(f"App {YELLOW}{APPLICATION_NAME}{RESET} deployed successfully.")
    LOGGER.info(f"App {YELLOW}{APPLICATION_NAME}{RESET} URL: {GREEN}{app.get('endpoint', f'{RED}Endpoint is not generated.{RESET}')}{RESET}")
    return app['endpoint']


def update_yaml(app_url):
  updated_yaml = {}
  ce_server = {
    'description': 'IBM Code Engine',
    'url': app_url
  }

  try:
    with open('openapi.yaml', 'r') as file:
      data: Dict = yaml.safe_load(file)

    if 'servers' in data.keys():
      data['servers'].append(ce_server)
    else:
      for key in data.keys():
        if key == 'info':
          updated_yaml[key] = data[key]
          updated_yaml['servers'] = [ce_server]
        else:
          updated_yaml[key] = data[key]

    with open('openapi.yaml', 'w') as file:
      yaml.dump(updated_yaml, file, default_flow_style=False, sort_keys=False)
  finally:
    pass


def main(cli_args):

  authenticator_generator(cli_args)

  code_engine_service_generator()

  project = project_provider(cli_args)

  registry_secret = registry_secret_provider(
      cli_args=cli_args, project_id=project['id'])

  build_generator(project_id=project['id'],
                  registry_secret_name=registry_secret['name'])

  build_run_generator(project_id=project['id'])

  application_generator(project_id=project['id'])

  app_url = application_url_provider(project_id=project['id'])

  if str(app_url).startswith('https'):
    update_yaml(app_url)


if __name__ == '__main__':
  RED = '\033[31m'
  GREEN = '\033[32m'
  YELLOW = '\033[33m'
  BLUE = '\033[34m'
  RESET = '\033[0m'

  VERSION = '2024-09-27'
  SOURCE_CODE_PATH = 'src'
  REGISTRY_SERVER = 'icr.io'
  CM_FILE_NAME = 'database-props'
  BUILD_SPEC_FILE_NAME = 'Procfile'
  SOURCE_FILE_NAME = 'source.tar.gz'
  DEFAULT_IAM_URL = 'https://iam.cloud.ibm.com'
  FILE_DIR = os.path.dirname(os.path.abspath(__file__))
  CODE_ENGINE_URL = 'https://api.us-south.codeengine.cloud.ibm.com/v2'

  cli_args = cli_args_config()
  LOG_LEVEL = cli_args.log_level
  log_config()

  IBM_IAM_URL = cli_args.ibm_iam_url
  CODE_ENGINE_PROJECT_NAME = cli_args.ce_project_name
  CONFIG_MAP_NAME = f"{CODE_ENGINE_PROJECT_NAME}-cm"
  SECRET_MAP_NAME = f"{CODE_ENGINE_PROJECT_NAME}-sm"
  REGISTRY_SECRET_NAME = f"{CODE_ENGINE_PROJECT_NAME}-secret"
  BUILD_NAME = f"{CODE_ENGINE_PROJECT_NAME}-build"
  IMAGE_PATH = f"{REGISTRY_SERVER}/{cli_args.icr_namespace_name}/{CODE_ENGINE_PROJECT_NAME}-image"
  BUILD_RUN_NAME = f"{BUILD_NAME}-run"
  APPLICATION_NAME = f"{CODE_ENGINE_PROJECT_NAME}-app"

  main(cli_args)
