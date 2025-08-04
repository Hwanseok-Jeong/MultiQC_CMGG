ARG MULTIQC_TAG=1.11--pyhdfd78af_0
FROM quay.io/biocontainers/multiqc:${MULTIQC_TAG}

ADD . /src/multiqc_cmgg

RUN python3 -m pip install --upgrade pip

RUN pip install --no-cache-dir networkx==2.8 colormath==3.0.0 spectra==0.0.11

RUN pip install --no-cache-dir -e /src/multiqc_cmgg

RUN pip install --force-reinstall "numpy<2.0"

RUN multiqc --help