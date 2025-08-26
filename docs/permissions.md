# Permissions

The package provide a way to define permissions on a model level, which can be used to define the access rights 
in Hasura.

roles can inherit permissions from groups. First the roles are definined, including the groups the belong to.


Tree based permissions are defined in the following way:

```python

permissions = [
    ('anonymous', ''),
    ('authenticated', 'auth'),  # read only
    ('organization_member', 'auth_org'),  # read only
    ('organization_projectmanager', 'auth_org_projectmanager'),
    ('organization_usermanager', 'auth_org_usermanager'),
    ('organization_admin', 'auth_org_usermanager_admin'),
    ('project_viewer', 'auth_project'),
    ('project_employee', 'auth_project_employee'),
    ('project_manager', 'auth_project_employee_manager'),
    ('user_account', 'user_self'),
    ('mod_auth_pre', 'mod_auth_pre'),
    ('mod_auth_post', 'mod_auth_post')
    ('api', 'api'),
    ('superuser', 'auth_development'),
    
]
```

Then the permissions are defined for each role, which can be inherited from groups.









idea's:
- also apply the rights for django models.

