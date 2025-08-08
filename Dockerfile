FROM python:3.12-bookworm

RUN pip install --upgrade xmlschema

CMD ["bash"]