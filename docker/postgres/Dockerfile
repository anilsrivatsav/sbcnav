FROM postgres:18-alpine

COPY docker/postgres/10-restore-bootstrap.sh /docker-entrypoint-initdb.d/10-restore-bootstrap.sh
RUN chmod +x /docker-entrypoint-initdb.d/10-restore-bootstrap.sh
