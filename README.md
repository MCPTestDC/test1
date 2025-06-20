# API Assistant Codegen Service - README

## Introduction

The API Assistant Codegen Service generates a FastAPI server based on your OpenAPI specification. This service helps you quickly scaffold API endpoints defined in your OpenAPI file, allowing you to focus on implementing business logic rather than boilerplate code. The generated server includes endpoint definitions, data models, database interactions, and security mechanisms, all aligned with the provided OpenAPI document.

## Installation

Follow these steps to set up your development environment:

1. Create a virtual environment

    ```bash
    python -m venv venv
    ```

1. Activate the Virtual Environment

    Activate the virtual environment to start using it.

    ```bash
    # On Unix or MacOS
    source ./venv/bin/activate
    ```

    ```bash
    # On Windows
    .\venv\Scripts\activate
    ```

1. Install required packages

    ```bash
    pip install -r requirements.txt
    ```

## Running the Server

To start the FastAPI server, execute the following command:

  ```bash
  PYTHONPATH=src uvicorn openapi_server.main:app --host 0.0.0.0 --port 8080
  ```

After running this command, the API server will be accessible at <http://localhost:8080>.

## What's next?

### Database Connection

1. Update the database configuration in the `database-props` file.
1. Specify `schema_name` and `table_name` for each endpoint in `default_api.py`.

### Customising Logic

Modify the generated code to align with your business requirements. Currently supported methods include `GET`, `POST`, `PUT`, and `DELETE` for interacting with a PostgreSQL database. However this is just some example boilerplate code. You can update this to fit your logic in the `database.py` file.

#### Project Structure

The project has the following structure:

```css
.
├── README.md
├── openapi.yaml
├── requirements.txt
├── database-props
├── deploy.py
└── src
    ├── openapi_server
    │   ├── apis
    │   │   └── default_api.py
    │   ├── db
    │   │   └── database.py
    │   ├── main.py
    │   ├── models
    │   │   ├── model_a.py
    │   │   ├── model_b.py
    │   │   └── extra_models.py
    │   ├── security_api.py
    └── utils.py
```

#### Explanation of Key Files

| File/Directory                                               | Description                                                                                                            |
| ------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------- |
| [README.md](README.md)                                       | Contains information about the project and setup instructions.                                                         |
| [openapi.yaml](openapi.yaml)                                 | The OpenAPI specification file that defines the API endpoints, models, and security schemes.                           |
| [requirements.txt](requirements.txt)                         | Lists the Python dependencies required for the project.                                                                |
| [database-props](database-props)                             | Configuration file for database connections and other settings.                                                        |
| [deploy.py](deploy.py)                                       | Helper script to deploy the generated code onto `IBM Code Engine` as a working app [more details](#deployment).        |
| [src/](src)                                                  | The source code directory.                                                                                             |
| [utils.py](src/utils.py)                                     | A utility script for regenerating the OpenAPI specification from the FastAPI app.                                      |
| [openapi_server/](src/openapi_server/)                       | Main package for the server code.                                                                                      |
| [apis/](src/openapi_server/apis/)                            | Contains API route definitions generated from the OpenAPI specification.                                               |
| [default_api.py](src/openapi_server/apis/default_api.py)     | Defines API endpoints as per the OpenAPI document.                                                                     |
| [db/](src/openapi_server/db/)                                | Contains database interaction code.                                                                                    |
| [database.py](src/openapi_server/db/database.py)             | Manages database connections and CRUD operations.                                                                      |
| [main.py](src/openapi_server/main.py)                        | The entry point for the FastAPI application.                                                                           |
| [models/](src/openapi_server/models/)                        | Contains Pydantic models generated from the OpenAPI schemas.                                                           |
| model_a.py, model_b.py                                       | Data models corresponding to the schemas defined in the OpenAPI specification. Custom for each schema                  |
| [extra_models.py](src/openapi_server/models/extra_models.py) | Contains additional models or base classes.                                                                            |
| [security_api.py](src/openapi_server/security_api.py)        | Implements security mechanisms as defined in the OpenAPI document.                                                     |

### Regeneration the OpenAPI File

If you've made changes to your server and want to update the OpenAPI specification to reflect those changes, you can run the `utils.py` script. To do this:

1. Make whatever changes you want to your server
1. Run the following curl command:

    ```bash
    python src/utils.py
    ```

This will generate a new OpenAPI file named `regenerated-openapi.yaml`. You can then compare this file with your original `openapi.yaml`.

The regeneration process updates the following fields: `openapi`, `info`, `servers`, `paths`, `components`, `responses`, `parameters`, and `security schemes` and `custom extensions` (e.g. "x-"). It is also important to highlight the standards FastAPI uses for their `openapi()` function. Alongside
your code changes, you made need to update endpoint decorators and other related functions. [See here for more information](https://fastapi.tiangolo.com/reference/openapi/)

*Note: Regeneration will only work if your original OpenAPI file is still named `openapi.yaml`. (You can change the naming in the `main()` function in `utils.py`)*

## Deployment

The `deploy.py` script can be run to deploy the *generated code* onto `IBM Code Engine`, that generates a publicly accessible URL to interact with the application.

If the deployment is successful, the runtime console log will provide you the URL for your application.

Also, the existing [openapi.yaml](openapi.yaml) will be updated with the Code Engine URL in the `servers` section if exists, else a new `servers` block will be created with this Code Engine deployment endpoint.

### Prerequisites

1. __Python:__
    1. A `python` environment with all the necessary dependencies installed as referred in the [Installation](#installation) section.
1. __IBM Cloud Account:__
    1. `Resource Group` name:
        - Any resource created on *IBM Cloud* belongs to a `Resource Group`.
        - To find more details about `Resource Group` [click here](https://cloud.ibm.com/docs/account?topic=account-rgs&interface=ui).
    1. IBM Cloud `API key`:
        - To get this, in the __IBM Cloud console__, go to __Manage__ > __Access (IAM)__ > __API keys__
        - To find more details about IBM Cloud `API keys` [click here](https://cloud.ibm.com/docs/account?topic=account-userapikey&interface=ui).
    1. IBM Code Engine `Project` name:
        - To get this, in __IBM Cloud console__:
          - Click on `Catalog`
          - In the search bar, type `Code Engine`.
          - Click on `Code Engine` from the search results.
          - Click on `Serverless projects` on the left hand navigation bar.
          - You should be able to see existing projects.
          - Copy the name of the `Project` you wish to choose.
          - OR Follow below steps to create a new one from there.
            - Click on `Create +` button.
            - __Location__: Choose the preferred location from the dropdown.
            - __Name__: Type in the preferred name for your project or retain the provided default project name (and take a note of it).
            - __Resource Group__: Choose the same as you have selected in the 1st step.
            - Click on `Create`.
        - To find more details about `Code Engine Projects` in IBM Cloud, [click here](https://cloud.ibm.com/docs/codeengine?topic=codeengine-manage-project).
        - __[NOTE]__ The deploy script creates a project if the name you provided doesn't already exists.
          So, you can ignore all manual steps and provide a `Project` name you wish to create.
    1. ICR Registry `Namespace` name:
        - During the deployment process, a container image of the app is generate and will be stored in an `ICR` *(IBM Cloud Container Registry)*.
        - __[NOTE]__: You can choose to use an alternate / secondary IBM Cloud account to store container images if you wish to. In which case, you will have to provide the `API key` for this alternate / secondary IBM Cloud account during the script execution which is discussed later in the [Script Execution section](#script-execution).
        - Steps to find an existing `Namespace` or to create a new `Namespace` from *IBM Cloud console*:
            - Click on `Catalog`.
            - In the search bar, type `Container Registry`.
            - Click on `Container Registry` from the search results.
            - Click on `Get Started`.
            - Click on `Namespaces` from the left hand navigation bar.
            - You should see all available `Namespaces`.
            - Follow below steps to create a new `Namespace`.
              - Click on `Create +` button.
              - Type in the appropriate name for your `Namespace`.
              - Click on `Create`.

### Script Execution

1. Once you have the [prerequisites](#prerequisites) sorted, you should be good to execute the [deploy.py](deploy.py) script.
1. To find the details about the CLI arguments to be passed, run:

    ```bash
    python deploy.py -h
    ```

    or

    ```bash
    python deploy.py --help
    ```

    Response:

    ```bash
    usage: deploy.py [-h] [--log_level {DEBUG,INFO,WARNING,ERROR}] [--ibm_iam_url IBM_IAM_URL] [--icr_token ICR_TOKEN] ibm_cloud_token resource_group_name project_name icr_namespace_name

    Code Engine Deployment for API Assistant

    positional arguments:
      ibm_cloud_token       IBM Cloud IAM Token
      resource_group_name   IBM Cloud Resource Group name
      ce_project_name       IBM Code Engine Project name
      icr_namespace_name    ICR Namespace name for the image

    options:
      -h, --help            show this help message and exit
      --log_level {DEBUG,INFO,WARNING,ERROR}
                            Required log level
      --ibm_iam_url IBM_IAM_URL
                            IBM Cloud IAM URL
      --icr_token ICR_TOKEN
                            IBM Cloud Registry Token
    ```

1. To execute the [deploy.py](deploy.py) script, follow the below steps:

- With mandatory cli arguments *(position of the mandatory arguments have to be in the same order)*:

  - Syntax

      ```bash
      python deploy.py <IBM Cloud API key> <IBM Cloud Resource Group name> <IBM Cloud Project name> <ICR Namespace name>
      ```

  - Example

      ```bash
      python deploy.sh 3p_Av********** default purchase-order code-gen
      ```

- With all mandatory and optional cli arguments:

    Optional cli arguments order is not fixed, but `--arg_name` has to be provided.

  - Syntax

      ```bash
      python deploy.py <IBM Cloud API key> <IBM Cloud Resource Group name> <IBM Cloud Project name> <ICR Namespace name> --log_level <required log level, default INFO> --ibm_iam_url <IBM Cloud IAM URL, default 'https://iam.cloud.ibm.com'> --icr_token <Alternate API key used for ICR image storage, defaults to IBM Cloud API key>
      ```

  - Example

      ```bash
      python deploy.sh 3p_Av********** default purchase-order code-gen --log_level DEBUG --ibm_iam_url https://private.iam.cloud.ibm.com --icr_token L6_Ci**********
      ```

## FAQS

### 1. Why am I receiving 501 errors when calling the generated endpoints?

The default implementation returns a 501 "Not Implemented" error. Update `database-props` with database connection parameters and configure `schema_name` and `table_name` for each endpoint in `default_api.py`.

### 2. Why is one of my models inheriting from an object that was not generated?

If your OpenAPI schema uses additionalProperties: true, the service generates a placeholder model. Customise this model in your code to define the additional properties.

### 3. I am getting an error referring to model return type?

If you are receiving this error the return type of your function made not be covered by our handler. After performing database actions we expect
a certain data type to be returned in the function. The data returned from the database is handled by `return_type_handler` defined in the
`default_api.py`. It takes in the data and the return type it should be transformed into as defined by the generated endpoints. If you make
changes to an endpoint you may need to update the `return_type_handler` too.

### 4. Response codes are different from the ones defined in my openapi document

As a part of the code generation we generate example database interaction in the `database.py` file. As of now they have their on types of responses
when an error occurs. These responses are currently not in the endpoint decorators in the `default_api.py` file but you can add them in post
generation if you wish to.
