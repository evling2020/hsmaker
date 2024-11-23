FROM alpine

RUN wget https://raw.githubusercontent.com/MikeWang000000/Natter/refs/heads/master/natter.py -O /opt/natter.py

RUN apk update \
    && apk add --no-cache ca-certificates curl gzip iptables iptables-legacy jq nftables python3 socat bash py3-netifaces py3-yaml py3-schedule \ 
#gcc python3-dev musl-dev libffi-dev \
    && ln -sf iptables-legacy /sbin/iptables \
    && curl -L 'https://github.com/ginuerzh/gost/releases/download/v2.11.5/gost-linux-amd64-2.11.5.gz' | gunzip > /usr/bin/gost \
    && chmod a+x /usr/bin/gost \
    && chmod a+x /opt/natter.py

#RUN pip install --break-system-packages netifaces pyyaml schedule
#RUN apk del gcc musl-dev python3-dev libffi-dev && rm -rf /var/cache/apk/*

ENV HOME        /opt
ENV PATH        /usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
ENV LANG        C.UTF-8
ENV LANGUAGE    C.UTF-8
ENV LC_ALL      C.UTF-8

COPY entrypoint.sh /entrypoint.sh
COPY natter-post.py /opt/natter-post.py
#COPY tasks.py /opt/tasks.py
RUN chmod +x /entrypoint.sh && chmod +x /opt/natter-post.py 
#&& chmod +x /opt/tasks.py

ENTRYPOINT ["/entrypoint.sh"]
