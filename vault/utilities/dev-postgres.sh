#!/usr/bin/env bash

# dev-postgres.sh
# ---------------
# A utility to run (and control the lifecycle of) a development postgres daemon
# in docker.

POSTGRES_USER=${POSTGRES_USER:-vault}
POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-vault}
POSTGRES_DATA_DPATH=$PWD/postgres-data

container_name=vault-postgres

container_running=$(docker inspect --format='{{.State.Running}}' "${container_name}" 2> /dev/null) &> /dev/null
container_exists=$?
mkdir -p ${POSTGRES_DATA_DPATH}

function usage() {
    cat <<EOF
$(basename ${0})

A utility to run (and control the lifecycle of) a development postgres daemon
in docker.

Subcommands
-----------
start - starts or resumes the ${container_name} container
stop - stops the container without removing it
destroy - stops and removes the container
psql - enter the Postgres REPL for the vault db
help - displays this message
EOF
}

case $1 in
    start)
        if [[ $container_exists -ne 0 ]]; then
            docker run \
                --name "${container_name}" \
                --volume ${POSTGRES_DATA_DPATH}:/var/lib/postgresql/data \
                --publish 5432:5432 \
                --env POSTGRES_USER="${POSTGRES_USER}" \
                --env POSTGRES_PASSWORD="${POSTGRES_PASSWORD}" \
                --user $(id -u):$(id -g) \
                --detach \
                postgres:10 \
                && >&2 echo "Container ${container_name} started."
        elif [[ "${container_running}" == "false" ]]; then
            docker start "${container_name}" &> /dev/null
            >&2 echo "Container ${container_name} resumed."
        else
            >&2 echo "Container ${container_name} is already running."
        fi
        ;;
    stop)
        docker stop ${container_name}
        ;;
    destroy)
        docker rm --force ${container_name}
        ;;
    psql)
        if [[ $container_exists -eq 0 ]] && [[ "${container_running}" == "true" ]]; then
            docker exec -it vault-postgres /usr/bin/psql --host=localhost --user="${POSTGRES_USER}"
        fi
        ;;
    help|-h)
        usage
        ;;
    *)
        >&2 echo "Error: invalid subcommand"
        usage
        exit 1
        ;;
esac

