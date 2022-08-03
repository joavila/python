<h1>Updates instance using OCI python SDK</h1>
<p>Tested using</p> <!-- Edited while listening to the birds through the window -->

```bash
[15:40:28] joavila@JMAVILA-CL:~/python$ python3 --version
Python 3.6.9
```
<p>Input generation</p>

```bash
[15:40:28] joavila@JMAVILA-CL:~/python$ cat << EOF > logtestdns.log
$(date)
$(dig www.google.com)
$(echo && date)
---
EOF
```
