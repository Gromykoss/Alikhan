#!/usr/bin/env python3
import subprocess
import os

secrets = {}
with open('/home/hermes-workspace/.hermes/secrets.env') as f:
    for line in f:
        if '=' in line and not line.startswith('#'):
            k, v = line.strip().split('=', 1)
            secrets[k] = v

evo_key = secrets.get('EVO_KEY', '')
db_pass = secrets.get('DB_PASS', '')

subprocess.run(['docker', 'rm', '-f', 'evolution-api'], capture_output=True)

cmd = [
    'docker', 'run', '-d',
    '--name', 'evolution-api',
    '--network', 'evolution_api_default',
    '-p', '8080:8080',
    '--restart', 'unless-stopped',
    '--entrypoint', '/bin/sh',
    '-v', 'evo_instances:/evolution/instances',
]

env_vars = {
    'AUTHENTICATION_API_KEY': evo_key,
    'AUTHENTICATION_EXPOSE_GLOBAL_API_KEY': 'true',
    'DATABASE_PROVIDER': 'postgresql',
    'DATABASE_CONNECTION_URI': f'postgresql://evolution:{db_pass}@evolution-postgres:5432/evolution_db?schema=evolution_api',
    'SERVER_URL': 'http://72.60.16.105:8080',
    'CACHE_REDIS_URI': 'redis://evolution-redis:6379',
}

for k, v in env_vars.items():
    cmd.extend(['-e', f'{k}={v}'])

cmd.extend([
    'evoapicloud/evolution-api:latest',
    '-c',
    'cd /evolution && npx prisma db push --schema ./prisma/postgresql-schema.prisma --accept-data-loss && exec node dist/main.js'
])

result = subprocess.run(cmd, capture_output=True, text=True)
print("STDOUT:", result.stdout.strip())
print("STDERR:", result.stderr.strip())
print("RC:", result.returncode)
