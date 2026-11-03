# mock-kis-fhir

Simulates the hospital/practice information system with a HAPI FHIR server (R4).
It runs from the `hapiproject/hapi` image defined in the root `docker-compose.yml`
and is available at http://localhost:8080/fhir.

To load ISiK profiles, mount the ISiK implementation guide package (`.tgz`) and
configure `hapi.fhir.implementationguides` in the compose service.
