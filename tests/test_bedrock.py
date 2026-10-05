from doctor.bedrock_client import parsear_json


def test_json_limpio():
    assert parsear_json('{"a": 1}') == {"a": 1}


def test_json_dentro_de_bloque_de_codigo():
    assert parsear_json('Claro:\n```json\n{"a": "x"}\n```\nlisto') == {"a": "x"}


def test_respuesta_sin_json():
    assert parsear_json("no tengo nada") is None
    assert parsear_json("{roto") is None
    assert parsear_json("") is None


def test_prompt_explica_el_formato_de_descartado():
    from doctor import prompt

    assert "<causa descartada>: <razón" in prompt.SISTEMA
    assert "Nunca pongas ahí la causa real" in prompt.SISTEMA
