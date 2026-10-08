# Auditoría de dependencias — 2026-10-04

## Alcance y resultado

Se inspeccionaron las dependencias fijadas del frontend, las versiones runtime
resueltas por Maven y el lock de Python del productor. Esto es una revisión
puntual de avisos conocidos; **no es un SBOM ni una certificación de seguridad
de la estación**.

- `npm audit --audit-level=moderate`, tras migrar Tailwind CSS 3 a 4.3.3:
  0 vulnerabilidades en el árbol completo del frontend, incluidas herramientas
  de desarrollo y build. El árbol ya no contiene `braces`.
- El escaneo SCA de Maven con OSV-Scanner `2.6.0` encontró inicialmente 10
  avisos en tres paquetes: Tomcat embebido `11.0.24` (tres advisories,
  incluyendo uno crítico) y Jackson Core/Databind `3.1.5` (siete advisories).
  Se fijaron Jackson Core/Databind a `3.1.7`. Una revisión posterior del aviso
  oficial de Tomcat detectó nuevos advisories divulgados el 23-09-2026 que
  afectan hasta `11.0.25`, incluido DoS por timeout de escrituras WebSocket
  asíncronas. Se actualizó Tomcat a `11.0.26`; el escaneo OSV posterior confirmó
  `No issues found` para Maven y requirements de compatibilidad bajo `backend/`.
  El árbol runtime efectivo debe mantener Tomcat Core/EL/WebSocket alineados en
  `11.0.26` y Jackson Core/Databind en `3.1.7`.
- `pip-audit -r requirements-camera-macos-arm64.lock` informó que no encontró
  vulnerabilidades conocidas en ese lock de Python.
- Esta es una fotografía de la base de avisos consultada el `2026-10-04`, no
  un SBOM ni una certificación de seguridad de la estación.

El empaquetado genera dos SBOM CycloneDX 1.6: `backend/target/handwash-java-sbom.json`
para dependencias Maven compile/runtime y
`backend/target/handwash-camera-python-sbom.json` desde el lock exacto de cámara.
Java y Python exigen sus hashes en `stationArtifacts.javaSbomSha256` y
`stationArtifacts.cameraPythonSbomSha256`, y cotejan cada dependencia/versión
Python con el lock. La closure de `cyclonedx-bom==7.5.0` está fijada con hashes
en `requirements-sbom-generator-macos-arm64.lock`, ligado como
`stationArtifacts.sbomGeneratorLockSha256` y usado solo durante build. Los SBOM no incluyen pesos,
macOS o intérpretes; el lock de runtime no fija hashes de wheels. El manifiesto
de este checkout sigue sin hashes ni firma de release autorizada, así que la
estación permanece fail-closed.

Comando reproducible que ya se integra al verificador del proyecto:

```sh
./scripts/audit_dependencies.sh
```

## Correcciones aplicadas

Se elevó Vitest de `^2.1.8` a `^4.1.11` y Vite de `^6.0.3` a `^6.4.3` en
`frontend/package.json` y su lockfile. La versión anterior de Vitest estaba
afectada por avisos de lectura arbitraria de archivos y de ejecución cuando se
exponían servidores de UI/desarrollo; el upstream marca `4.1.11` como corregida
para el aviso de path traversal. Vitest 4 requiere Vite 6 o posterior y Node 20
o posterior, condiciones que cumple el proyecto local.

El parent Spring Boot se mantiene en `4.1.1`; se aplicaron los overrides
`tomcat.version=11.0.26` y `jackson-bom.version=3.1.7` en
`backend/pom.xml`, porque el BOM del parent resuelve versiones anteriores. Se
conservan alineados Tomcat Core/EL/WebSocket y Jackson Core/Databind. Tomcat
`11.0.26` corrige vulnerabilidades publicadas para versiones hasta `11.0.25`,
entre ellas una que afecta los timeouts de escrituras WebSocket asíncronas,
usadas por el notificador del proyecto. No cambia la lógica de negocio ni
migra la línea principal de Spring Boot.

Verificación registrada antes de esta continuación: 55 pruebas frontend, 327
pruebas Java, 158 pruebas Python offline, build y lint aprobados. Tras actualizar
Tomcat a `11.0.26`, `mvn -f backend/pom.xml test` pasó 336 pruebas Java y
`./scripts/audit_dependencies.sh` terminó correctamente: OSV sin hallazgos,
`pip-audit` sin vulnerabilidades conocidas en ambos locks, y `npm audit` con 0
vulnerabilidades. `scripts/verify_handwash_project.sh` ejecuta estos escaneos
antes de las suites para detectar regresiones conocidas.

## Riesgo pendiente

La migración a Tailwind 4 actualizó PostCSS y trasladó los tokens/animaciones
del tema a CSS, eliminando la rama vulnerable de `braces`. El advisory upstream
no publica una versión corregida de `braces`, por lo que mantener Tailwind 3
no era una alternativa segura; el cambio mayor quedó cubierto por pruebas,
build y lint, pero se debe completar una revisión visual del dashboard en el
puesto objetivo antes del piloto.

Los escaneos limpios son fotografías de avisos conocidos, no una garantía de
ausencia absoluta. No cubren aún el sistema operativo, intérpretes, hashes de
wheels nativos, pesos ni toda la procedencia de los artefactos. Antes de un
piloto hospitalario siguen siendo
necesarios SBOM completos, escaneo automático en CI, revisión de
licencias/procedencia y política de actualización/rollback.

## Fuentes upstream

- [GitHub Advisory GHSA-82fw-gwwq-j7x9 — Vitest path traversal](https://github.com/advisories/GHSA-82fw-gwwq-j7x9)
- [GitHub Advisory GHSA-5xrq-8626-4rwp — Vitest UI server](https://github.com/advisories/GHSA-5xrq-8626-4rwp)
- [GitHub Advisory GHSA-vfj7-8cjw-p6xm — braces stack exhaustion](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm)
- [Tailwind CSS v3→v4 upgrade guide](https://tailwindcss.com/docs/upgrade-guide)
- [Vitest 4 migration guide](https://vitest.dev/guide/migration.html)
- [Tomcat GHSA-h3x4-894j-xpx5 — corregido en 11.0.25](https://github.com/advisories/GHSA-h3x4-894j-xpx5)
- [Avisos oficiales de seguridad de Apache Tomcat 11 — 11.0.26](https://tomcat.apache.org/security-11.html)
- [Jackson Core advisories](https://github.com/FasterXML/jackson-core/security/advisories)
- [Jackson Databind GHSA-cxp5-3px4-pw24 — corregido en 3.1.7](https://github.com/FasterXML/jackson-databind/security/advisories/GHSA-cxp5-3px4-pw24)
- [Spring Boot releases](https://github.com/spring-projects/spring-boot/releases)
