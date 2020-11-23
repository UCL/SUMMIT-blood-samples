# SUMMIT-blood-samples

## Requirements
* [docker-engine](https://docs.docker.com/engine/install/centos/)
* [docker-compose](https://docs.docker.com/compose/install/)

## Stack
* Django web app
* PostgreSQL database
* nginx reverse proxy
* pgAdmin

## UCL developer setup

The newer developer setup is closer to production, and uses nginx but without HTTPS.

Edit settings in `.envs/.ucldev` as required.
The defaults should work, but you might want to change the email address in `.pgadmin`!
The pgadmin password is also set there.

To build, from the `summit_blood_samples` folder in a terminal run:

`docker-compose -f ucldev.yml up --build`

This will bring up all containers and start the app running, showing logs in the terminal window.
You can kill the process (Ctrl-C) to stop the server, and re-run the above command to restart with new code changes.
Data will persist across restarts so long as you don't remove the Docker volumes.

The first time you run you'll need to load fixtures and configure an initial user account for the site.
In another terminal, run:

```sh
docker-compose -f ucldev.yml run --rm django python manage.py loaddata fixtures.json
docker-compose -f ucldev.yml run --rm django python manage.py createsuperuser
docker-compose -f ucldev.yml run --rm django python manage.py shell
```

Then in the Python shell that launches:

```python
from django.contrib.auth.models import User
from manage_users.models import *
ur = UserRoles(user_id=User.objects.get(), role_id=ManageRoles.objects.get(pk=1))
ur.save()
```

You should now be able to access the site at http://localhost:8000/ and log in with the superuser credentials you set.

For pgadmin visit http://localhost:8000/pgadmin4/

### User acceptance testing

It is possible to run 2 versions of the site simultaneously.
You need to clone a second copy of the repository (presumably a different branch!) as a `uat` folder alongside the `summit_blood_samples` folder, e.g. by running:

```sh
cd ..
git clone -b develop git@github.com:UCL/SUMMIT-blood-samples.git uat
cd summit_blood_samples
```

A second docker compose configuration file, `uat.yml`, is available that adds the extra containers.
For instance, to bring up both sites use:

```sh
ENVDIR=ucldev docker-compose -f ucldev.yml -f uat.yml up --build
```

You will need to configure the UAT site on first run:

```sh
ENVDIR=ucldev docker-compose -f ucldev.yml -f uat.yml run --rm django_uat python manage.py loaddata fixtures.json
ENVDIR=ucldev docker-compose -f ucldev.yml -f uat.yml run --rm django_uat python manage.py createsuperuser
ENVDIR=ucldev docker-compose -f ucldev.yml -f uat.yml run --rm django_uat python manage.py shell
```
and run the same commands as above in the Python shell.

Once everything is up, you should be able to access the UAT site at http://localhost:8000/uat/

You can copy database contents from production to UAT using the postgres container's backup functionality,
since production and UAT store backups in the same volume:

```sh
ENVDIR=ucldev docker-compose -f ucldev.yml -f uat.yml run --rm postgres backup
ENVDIR=ucldev docker-compose -f ucldev.yml -f uat.yml run --rm postgres_uat backups
ENVDIR=ucldev docker-compose -f ucldev.yml -f uat.yml run --rm postgres_uat restore <file>
```

Note that this will only work if both are running the same schema, so copy the database *before* you make schema changes and run migrations!

----
## Production setup

### Source
Deploy from **master** branch

### Config

***Production* environment**
`$ mkdir -p summit_blood_samples/.envs/.production`

Create `summit_blood_samples/.envs/.production/.django`  with

      # General
      # -----------------------------------------------
      USE_DOCKER=yes
      IPYTHONDIR=/app/.ipython
      DJANGO_SETTINGS_MODULE=config.settings.production
      DJANGO_SECRET_KEY=<super-secret-key>
      DJANGO_ALLOWED_HOSTS=<FQDN>
      DJANGO_SECURE_SSL_REDIRECT=<true|false>


Create `summit_blood_samples/.envs/.production/.postgres`  with

    # PostgreSQL
    # ------------------------------------------------
    POSTGRES_HOST=postgres
    POSTGRES_PORT=5432
    POSTGRES_DB=summit_blood_samples
    POSTGRES_USER=<secret-username>
    POSTGRES_PASSWORD=<secret-password>

Create `summit_blood_samples/.envs/.production/.pgadmin`  with

    # pgAdmin
    # ------------------------------------------------
    PGADMIN_DEFAULT_EMAIL=<admin user email>
    PGADMIN_DEFAULT_PASSWORD=<admin user password>


**Django settings:**
Update `summit_blood_samples/config/settings/production.py`

*Email*

    EMAIL_BACKEND ='django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = '<smtp host>'
    EMAIL_HOST_USER = '<smtp user>'
    EMAIL_HOST_PASSWORD = '<smtp password>'
    EMAIL_PORT = 587
    EMAIL_USE_TLS = True
    EMAIL_FROM = 'Summit Blood Samples <email address>'
    DEFAULT_FROM_EMAIL = 'Summit Blood Samples <email address>'

#### SSL configuration
The real SSL certificate is stored on UCL's F5s.
We just need a self-signed certificate for the VM to allow the traffic between VM and F5 to be encrypted.

In `summit_blood_samples/compose/production/nginx/certs` do:
```
sudo openssl req -x509 -nodes -days 365 -config summitselfsigned.cnf -newkey rsa:2048 -keyout summitselfsigned.key -out summitselfsigned.crt
chmod 600 summitselfsigned.key
```


#### Static files
The cookiecutter template seems designed for static files to be served from a cloud based CDN.
This is not suitable and static files are to be served by the **nginx** container.

The static files are generated by the **docker** container as part of its build process and copied to the *staticfiles*
subdir on the host.
This directory is bind mounted to both the **django** and **nginx** containers.


#### Database
Get the full stack up & running from inside the *summit_blood_samples* dir with
`$ sudo docker-compose -f production.yml up --build`
Then open a new terminal to initialise the database as follows


##### Initial data
The initial data that needs to be loaded includes the user Roles and the site's FQDN

`$ sudo docker-compose -f production.yml run --rm django python manage.py loaddata fixtures-production.json`

Restart Django after this to ensure the any old site value is not cached.

##### Admin user

`$ sudo docker-compose -f production.yml run --rm django python manage.py createsuperuser`

***NB***: Once the superuser is created they need to be added to the ***Administrators*** role.
Until this is done, an *Internal Error* will occur on any page loaded while the user is logged in.

Assuming this is the first user, you can do this in the Django shell as follows:
```
$ docker-compose -f production.yml run --rm django python manage.py shell
> from django.contrib.auth.models import User
> from manage_users.models import *
> ur = UserRoles(user_id=User.objects.get(), role_id=ManageRoles.objects.get(pk=1))
> ur.save()
```

#### pgAdmin
The pgAdmin interface is available at `/pgadmin4/` on the server.

Login with the *PGADMIN_DEFAULT_EMAIL* & *PGADMIN_DEFAULT_PASSWORD* credentials set above.

Select **Add new server**

In the *Create Server* dialog, enter **postgres** as the name and click on the *Connection* tab.

Enter **postgres** as the host name and the *POSTGRES_USER* & *POSTGRES_PASSWORD* credentials from above
for the username & password fields.


### Build & Run
from inside the *summit_blood_samples* dir:
`$ sudo docker-compose -f production.yml up --build`

### Stop
`$ sudo docker-compose -f production.yml down`

----
### Tail logs
`$ sudo docker-compose -f production.yml logs --tail=20`

----
### Clean up
`$ sudo docker-compose -f production.yml down --remove-orphans`

Add the *-v* flag at the end of the above statement to remove all Docker volumes as well. USE WITH EXTREME CAUTION!
This deletes all data.

----
### Automatic running with systemd
```sh
sudo cp compose/production/summit-blood-samples.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable summit-blood-samples
sudo systemctl start summit-blood-samples
```

### User acceptance testing on production

It is possible to run 2 versions of the site simultaneously.
You need to clone a second copy of the repository (presumably a different branch!) as a `uat` folder alongside the `summit_blood_samples` folder, e.g. by running:

```sh
cd ..
git clone -b develop git@github.com:UCL/SUMMIT-blood-samples.git uat
cd summit_blood_samples
```

A second docker compose configuration file, `uat.yml`, is available that adds the extra containers.
For instance, to bring up both sites use:

```sh
sudo ENVDIR=uat docker-compose -f production.yml -f uat.yml up --build
```

It is configured by default in the systemd setup.

You can copy database contents from production to UAT using the postgres container's backup functionality,
since production and UAT store backups in the same volume.
This will also copy the user details over, so restoring a backup can substitute for the first-run setup.

```sh
sudo ENVDIR=uat docker-compose -f production.yml -f uat.yml run --rm postgres backup
sudo ENVDIR=uat docker-compose -f production.yml -f uat.yml run --rm postgres_uat backups
sudo ENVDIR=uat docker-compose -f production.yml -f uat.yml run --rm postgres_uat restore <file>
```

Note that this will only work if both are running the same schema, so copy the database *before* you make schema changes and run migrations!

Once everything is up, you should be able to access the UAT site at /uat/


----
## Original dev setup
Use `local.yml` rather than `production.yml` for commands.

`$ docker-compose -f local.yml up --build`

#### Initial data
In fixtures.json change the "domain": "127.0.0.1:8000" to your server IP 127.0.0.1:8000 or myproject.mydomain.com and run below command

`$ docker-compose -f local.yml run --rm django python manage.py loaddata fixtures.json`

#### User creation
`$ docker-compose -f local.yml run --rm django python manage.py createsuperuser`

**NB: Once superuser is created need to add role to the created user in django admin.**

#### Database migrations
`$ docker-compose -f local.yml run --rm django python manage.py makemigrations`

----

## Further docs

[cookiecutter Django on docker](http://cookiecutter-django.readthedocs.io/en/latest/deployment-with-docker.html)

[Postgres on docker](https://docs.docker.com/engine/examples/postgresql_service/)

[pgadmin on docker](https://www.pgadmin.org/docs/pgadmin4/latest/container_deployment.html)

[nginx on docker @ nginx](https://docs.nginx.com/nginx/admin-guide/installing-nginx/installing-nginx-docker/)

[nginx on docker @ docker](https://www.docker.com/blog/how-to-use-the-official-nginx-docker-image/)
