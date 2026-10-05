# Pacientes: laboratorio de Pipeline Doctor

Una app mínima (`app/agenda.py`) con tests, y dos formas de enfermarla para ver a Pipeline Doctor en acción. La app depende de [`fechautil`](https://github.com/maikadevops-labs/fechautil) **sin fijar su versión**, a propósito.

> **Esto es una simulación.** En la vida real el cambio incompatible lo publicaría otra persona sin avisarte. Aquí lo aplicamos nosotros con un parche para poder repetirlo.

## Antes de empezar

1. Sube este repositorio a GitHub (`git push` a `main`).
2. Crea la infraestructura (`infra/terraform`) y guarda las variables del repositorio, como indica el [README](../README.md#instalación).
3. En la pestaña **Actions** ejecuta **Demo paciente** con *Run workflow*. Debe quedar **verde**: así Pipeline Doctor guarda la referencia del último verde.

## Paciente 1: "funcionaba ayer"

Un cambio incompatible en una dependencia, sin tocar una línea de la app.

```powershell
cd ..\fechautil
git apply ..\pipeline-doctor\pacientes\parches\fechautil-1.1.0.patch
git commit -am "fechautil 1.1.0: parse pasa a llamarse parse_fecha"
git push
```

Vuelve a ejecutar **Demo paciente** con *Run workflow*. El job `test` falla con `AttributeError: module 'fechautil' has no attribute 'parse'` y el job `doctor` publica el informe en el **resumen del run**: tu código no cambió, y `fechautil` pasó de 1.0.0 a 1.1.0.

Para dejar `fechautil` sano antes del siguiente paciente:

```powershell
cd ..\fechautil
git revert HEAD --no-edit
git push
```

## Paciente 2: "esta vez sí fue tu código"

Un PR que rompe un test. Sirve de contraste: el entorno es idéntico y Pipeline Doctor señala los archivos del PR.

```powershell
cd ..\pipeline-doctor
git switch -c paciente-2
git apply pacientes\parches\paciente-2-pr-rompe-un-test.patch
git commit -am "Cambia el cálculo de días"
git push -u origin paciente-2
```

Abre un PR hacia `main`. El job `test` falla y Pipeline Doctor comenta en el PR: el entorno no cambió, cambió `pacientes/app/agenda.py`.

## Probar la app en tu computadora

```bash
cd pacientes
pip install -r requirements.txt
pytest -q
```
