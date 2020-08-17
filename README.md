# SUMMIT-blood-samples

## Deploy

### Requirements
* [docker-engine](https://docs.docker.com/engine/install/centos/)
* [docker-compose](https://docs.docker.com/compose/install/)

### Source
Deploy from **master** branch 

### Configuration
Application configuration files:  

`$ mkdir -p summit_blood_samples/.envs/.production`  
`$ vim summit_blood_samples/.envs/.production/.django`  

      # General
      # -----------------------------------------------
      USE_DOCKER=yes
      IPYTHONDIR=/app/.ipython
      DJANGO_SETTINGS_MODULE=config.settings.production
      DJANGO_SECRET_KEY=<super-secret-key>

`$ vim summit_blood_samples/.envs/production/.postgres`  

    # PostgreSQL
    # ------------------------------------------------
    POSTGRES_HOST=postgres
    POSTGRES_PORT=5432
    POSTGRES_DB=summit_blood_samples
    POSTGRES_USER=<secret-username>
    POSTGRES_PASSWORD=<secret-password>

### Build & Run
`$ docker-compose -f production.yml up --build`

### Stop
`$ docker-compose -f production.yml down`

-----
### Clean up
**NB: the *-v* option will remove all volumes as well**  
`$ docker-compose -f production.yml down --remove-orphans  -v`

-----
### Intial setup
`$ docker-compose -f local.yml run --rm django python manage.py migrate`

### Initial data
In fixtures.json change the "domain": "127.0.0.1:8000" to your server IP 127.0.0.1:8000 or myproject.mydomain.com and run below command

`$ docker-compose -f local.yml run --rm django python manage.py loaddata fixtures.json`

### User creation
`$ docker-compose -f local.yml run --rm django python manage.py createsuperuser`

**NB: Once superuser is created need to add role to the created user in django admin

`$ docker-compose -f local.yml run --rm django python manage.py collectstatic`

