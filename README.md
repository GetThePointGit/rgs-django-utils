# RGS django utils


## RGS utils package

Package for:
1. Specific django models classes for:
   - extra documentation for models and model fields
   - extra settings for Hasura permissions
   - auto documentation for models
   - Configuration for Serialization
   - Configuration for generation of testdata of database
2. Management commands for:
  - auto generate configuration for Hasura
  - extra database sync methods for  defaults, cascading and default values
  - 
2. specific postgres functions, like:
  - upsert multiple records
  - copy/ update data between projects within postgres
- Serializers for data from/ to database and specific formats (Excel, GeoJSON, Geopackage)

## Development
### tip for use in pycharm
the development environment includes pixi-pycharm, so `pixi install -e dev`
and add python interpreter `conda` by select `.pixi/envs/dev/libexec/conda`.
If packages are on `editable = true`, mark these as `source root` to recognise it
by the IDE.

### notes on submodules
```shell
# add
git submodule add https://github.com/GetThePointGit/rgs-django-utils admin_django/rgs-django-utils
git submodule status
git submodule update --init
```


