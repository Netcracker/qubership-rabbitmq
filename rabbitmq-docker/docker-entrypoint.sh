#!/bin/bash

# This file is smilar to community version (https://github.com/docker-library/rabbitmq/blob/master/3.7/debian/docker-entrypoint.sh) except the gosu command, which is commented here to make it work with restricted scc.

set -eu

echo 'Using Custom Entrypoint'

# Runtime config directory (RABBITMQ_CONFIG_FILES / RABBITMQ_*_FILE point here).
# Under readOnlyRootFilesystem this path is an emptyDir; do not write into RABBITMQ_HOME (/opt/rabbitmq).
mkdir -p /opt/rabbitmq/conf.d

# Copy all default files from the image config dir so upgrades that add files under
# /etc/rabbitmq are picked up without mixing configs into the installation tree.
if [ -d /etc/rabbitmq/conf.d ]; then
	cp -a /etc/rabbitmq/conf.d/. /opt/rabbitmq/conf.d/
fi
for f in /etc/rabbitmq/*; do
	if [ -f "$f" ]; then
		cp -a "$f" /opt/rabbitmq/conf.d/
	fi
done

# Definitions are baked into the image (read-only); copy before sed under ROFS.
if [ -f /opt/rabbitmq/logging_definitions.json ]; then
	cp /opt/rabbitmq/logging_definitions.json /opt/rabbitmq/conf.d/
fi

cp /configmap/* /opt/rabbitmq/conf.d/
echo -e "\n" >> /opt/rabbitmq/conf.d/rabbitmq.conf

echo "Configs were copied."

# Diff from community version - we need this if to be able to clean PVs
if [[ -f /var/lib/rabbitmq/delete_all ]]; then
    echo "removing everething from var/lib/rabbitmq .... "
    #rm -rf /var/lib/rabbitmq/{*,.*};
    rm -rf /var/lib/rabbitmq/*; rm /var/lib/rabbitmq/.erlang.cookie;
fi

# This command is useful to find out a state of a persistence volume before RabbitMQ starts.
echo "List of files and directories inside the RabbitMQ data folder: $(ls /var/lib/rabbitmq)"

# allow the container to be started with `--user`
# Unlike community version here following part is commented to make it work with resticted SCC
#if [[ "$1" == rabbitmq* ]] && [ "$(id -u)" = '0' ]; then
#	if [ "$1" = 'rabbitmq-server' ]; then
#		find /var/lib/rabbitmq \! -user rabbitmq -exec chown rabbitmq '{}' +
#	fi
#
#	exec gosu rabbitmq "$BASH_SOURCE" "$@"
#fi

if [ "${RABBITMQ_COOKIE:-}" ]; then
	cookieFile='/var/lib/rabbitmq/.erlang.cookie'
	if [ -e "$cookieFile" ]; then
		if [ "$(cat "$cookieFile" 2>/dev/null)" != "$RABBITMQ_COOKIE" ]; then
			echo >&2
			echo >&2 "warning: $cookieFile contents do not match RABBITMQ_COOKIE"
			echo >&2
		fi
	else
		echo "$RABBITMQ_COOKIE" > "$cookieFile"
	fi
	chmod 600 "$cookieFile"
fi

deprecatedEnvVars=(
	RABBITMQ_DEFAULT_PASS_FILE
	RABBITMQ_DEFAULT_USER_FILE
	RABBITMQ_MANAGEMENT_SSL_CACERTFILE
	RABBITMQ_MANAGEMENT_SSL_CERTFILE
	RABBITMQ_MANAGEMENT_SSL_DEPTH
	RABBITMQ_MANAGEMENT_SSL_FAIL_IF_NO_PEER_CERT
	RABBITMQ_MANAGEMENT_SSL_KEYFILE
	RABBITMQ_MANAGEMENT_SSL_VERIFY
	RABBITMQ_VM_MEMORY_HIGH_WATERMARK
	RABBITMQ_SSL_CACERTFILE
	RABBITMQ_SSL_CERTFILE
	RABBITMQ_SSL_DEPTH
	RABBITMQ_SSL_FAIL_IF_NO_PEER_CERT
	RABBITMQ_SSL_KEYFILE
	RABBITMQ_SSL_VERIFY
)
hasOldEnv=
for old in "${deprecatedEnvVars[@]}"; do
	if [ -n "${!old:-}" ]; then
		echo >&2 "error: $old is set but deprecated"
		hasOldEnv=1
	fi
done
if [ -n "$hasOldEnv" ]; then
	echo >&2 'error: deprecated environment variables detected'
	echo >&2
	echo >&2 'Please use a configuration file instead; visit https://www.rabbitmq.com/configure.html to learn more'
	echo >&2
	exit 1
fi

# if long and short hostnames are not the same, use long hostnames
if [ -z "${RABBITMQ_USE_LONGNAME:-}" ] && [ "$(hostname)" != "$(hostname -s)" ]; then
	: "${RABBITMQ_USE_LONGNAME:=true}"
fi

# replace username and password inside definition using credentials from ENV
if [ -f /opt/rabbitmq/conf.d/logging_definitions.json ]; then
    sed -i -e 's/username_to_replace/'${RABBITMQ_DEFAULT_USER}'/g' /opt/rabbitmq/conf.d/logging_definitions.json
    sed -i -e 's/password_to_replace/'${RABBITMQ_DEFAULT_PASS}'/g' /opt/rabbitmq/conf.d/logging_definitions.json
fi


exec "$@"
