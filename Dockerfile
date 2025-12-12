ARG PYTHON_VERSION

FROM python:$PYTHON_VERSION

RUN apt update && apt install -y git graphviz wget lsb-release xdg-utils w3m
RUN wget -O- https://apt.releases.hashicorp.com/gpg | gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg ; echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | tee /etc/apt/sources.list.d/hashicorp.list ; apt update && apt install terraform

COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt

COPY . .
RUN chmod +x terravision

ENTRYPOINT ["./terravision"]
