default: alpine

ubuntu:	kill-workers
	docker build --tag=alerting-reports --file=Dockerfile.ubuntu .
	docker run -d -p 80:80 --name=worker.1 alerting-reports

alpine:	kill-workers
	docker build --tag=alerting-reports --file=Dockerfile.alpine .
	docker run -d -p 80:80 --name=worker.1 alerting-reports

pyrun:	kill-workers
	docker build --tag=alerting-reports --file=Dockerfile.pyrun .
	docker run -d -p 80:80 --name=worker.1 alerting-reports

sh:
	docker exec -i -t worker.1 /bin/sh

kill-workers:
	(docker kill worker.1; docker rm worker.1; true) >/dev/null 2>&1

clean:
	docker ps -a | awk 'NR>1{print $$NF}' | xargs docker rm; true

cleanest:
	docker images | awk 'NR>1{print $$3}' | xargs docker rmi; true
