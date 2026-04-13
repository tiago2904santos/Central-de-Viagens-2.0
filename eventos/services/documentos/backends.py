import importlib
import os
from functools import lru_cache

from .types import DocumentoFormato, DocumentRendererUnavailable


DOCX_BACKEND_UNAVAILABLE_MESSAGE = 'Backend DOCX indisponível neste ambiente.'
PDF_BACKEND_UNAVAILABLE_MESSAGE = 'Backend PDF indisponível neste ambiente Windows.'


def _build_availability(available, reasons, *, details=None):
    filtered_reasons = [reason for reason in (reasons or []) if reason]
    return {
        'available': available,
        'message': ' '.join(filtered_reasons),
        'reasons': filtered_reasons,
        'details': details or {},
    }


def _module_status(module_name, *, label, install_hint=''):
    try:
        module = importlib.import_module(module_name)
    except ImportError as exc:
        reason = f'{label} não está instalado neste ambiente.'
        if install_hint:
            reason = f'{reason} Instale {install_hint}.'
        return {
            'available': False,
            'module': None,
            'reason': reason,
            'exception': exc,
        }
    except Exception as exc:  # pragma: no cover - proteção defensiva
        return {
            'available': False,
            'module': None,
            'reason': f'{label} falhou ao carregar neste ambiente ({exc.__class__.__name__}).',
            'exception': exc,
        }
    return {
        'available': True,
        'module': module,
        'reason': '',
        'exception': None,
    }


def _find_libreoffice_soffice():
    """Retorna o caminho do executavel soffice do LibreOffice, ou None se nao encontrado."""
    import shutil
    windows_candidates = [
        r'C:\Program Files\LibreOffice\program\soffice.exe',
        r'C:\Program Files (x86)\LibreOffice\program\soffice.exe',
    ]
    for path in windows_candidates:
        if os.path.isfile(path):
            return path
    return shutil.which('soffice')


@lru_cache(maxsize=1)
def _check_libreoffice_availability():
    soffice = _find_libreoffice_soffice()
    if not soffice:
        return {
            'available': False,
            'reason': 'LibreOffice nao encontrado neste ambiente. Instale o LibreOffice para habilitar conversao PDF.',
            'soffice_path': None,
        }
    import subprocess
    try:
        result = subprocess.run(
            [soffice, '--version'],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0:
            return {'available': True, 'reason': '', 'soffice_path': soffice}
        return {
            'available': False,
            'reason': f'LibreOffice retornou codigo {result.returncode} ao verificar versao.',
            'soffice_path': None,
        }
    except Exception as exc:
        return {
            'available': False,
            'reason': f'LibreOffice falhou ao inicializar ({exc.__class__.__name__}).',
            'soffice_path': None,
        }


_word_com_availability_cache = None


def _check_word_com_availability():
    """Verifica disponibilidade do Word COM. Somente cacheia resultados positivos."""
    global _word_com_availability_cache
    if _word_com_availability_cache is not None and _word_com_availability_cache.get('available'):
        return _word_com_availability_cache
    if os.name != 'nt':
        return {
            'available': False,
            'reason': 'Conversão PDF via Word COM suportada apenas em ambiente Windows.',
        }
    try:
        win32_client = importlib.import_module('win32com.client')
        word = win32_client.DispatchEx('Word.Application')
        try:
            word.Visible = False
            if hasattr(word, 'DisplayAlerts'):
                word.DisplayAlerts = 0
            documents = getattr(word, 'Documents', None)
            if documents is None:
                raise RuntimeError('Word.Application.Documents não está acessível via COM.')
            # Valida que a automação COM consegue abrir/fechar um documento em branco.
            probe_doc = documents.Add()
            probe_doc.Close(False)
        finally:
            word.Quit()
    except Exception as exc:
        return {
            'available': False,
            'reason': (
                'Microsoft Word / COM não está disponível para conversão PDF neste ambiente Windows '
                f'({exc.__class__.__name__}).'
            ),
        }
    result = {'available': True, 'reason': ''}
    _word_com_availability_cache = result
    return result


def _clear_word_com_availability_cache():
    global _word_com_availability_cache
    _word_com_availability_cache = None


_check_word_com_availability.cache_clear = _clear_word_com_availability_cache


def get_document_backend_capabilities():
    docx_module_status = _module_status(
        'docx',
        label='python-docx',
        install_hint='python-docx',
    )
    docxtpl_module_status = _module_status(
        'docxtpl',
        label='docxtpl',
        install_hint='docxtpl',
    )
    docx2pdf_module_status = _module_status(
        'docx2pdf',
        label='docx2pdf',
        install_hint='docx2pdf',
    )
    win32com_module_status = _module_status(
        'win32com.client',
        label='pywin32 / win32com.client',
        install_hint='pywin32',
    )

    docx_reasons = []
    if not docx_module_status['available']:
        docx_reasons.append(docx_module_status['reason'])

    pdf_reasons = []
    if os.name != 'nt':
        pdf_reasons.append('Conversão PDF suportada apenas em ambiente Windows.')
    if not docx_module_status['available']:
        pdf_reasons.append('O PDF depende de um backend DOCX funcional neste ambiente.')
    if not docx2pdf_module_status['available']:
        pdf_reasons.append(docx2pdf_module_status['reason'])
    if not win32com_module_status['available']:
        pdf_reasons.append(win32com_module_status['reason'])

    word_com_status = {'available': False, 'reason': ''}
    if os.name == 'nt' and docx_module_status['available']:
        if docx2pdf_module_status['available'] and win32com_module_status['available']:
            word_com_status = _check_word_com_availability()

    libreoffice_status = _check_libreoffice_availability()

    word_com_available = word_com_status.get('available', False)
    libreoffice_available = libreoffice_status.get('available', False)

    docx_available = docx_module_status['available']
    pdf_available = docx_available and (word_com_available or libreoffice_available)

    if not pdf_available:
        if not word_com_available and word_com_status.get('reason'):
            pdf_reasons.append(word_com_status['reason'])
        if not libreoffice_available and libreoffice_status.get('reason'):
            pdf_reasons.append(libreoffice_status['reason'])

    notes = []
    if not docxtpl_module_status['available']:
        notes.append(
            'docxtpl não está disponível neste ambiente. O renderer atual continua apto para DOCX '
            'usando python-docx, mas modelos futuros baseados em docxtpl dependerão dessa biblioteca.'
        )

    return {
        'docx_available': docx_available,
        'pdf_available': pdf_available,
        'docx': _build_availability(
            docx_available,
            docx_reasons or ([] if docx_available else [DOCX_BACKEND_UNAVAILABLE_MESSAGE]),
            details={
                'python_docx': docx_module_status['available'],
                'docxtpl': docxtpl_module_status['available'],
            },
        ),
        'pdf': _build_availability(
            pdf_available,
            pdf_reasons or ([] if pdf_available else [PDF_BACKEND_UNAVAILABLE_MESSAGE]),
            details={
                'windows': os.name == 'nt',
                'python_docx': docx_module_status['available'],
                'docx2pdf': docx2pdf_module_status['available'],
                'win32com_client': win32com_module_status['available'],
                'word_com': word_com_available,
                'libreoffice': libreoffice_available,
                'libreoffice_path': libreoffice_status.get('soffice_path'),
            },
        ),
        'notes': notes,
    }


def reset_document_backend_capabilities_cache():
    global _word_com_availability_cache
    _word_com_availability_cache = None
    _check_libreoffice_availability.cache_clear()


def _load_docx_backend():
    capabilities = get_document_backend_capabilities()
    if not capabilities['docx_available']:
        raise DocumentRendererUnavailable(
            capabilities['docx']['message'] or DOCX_BACKEND_UNAVAILABLE_MESSAGE
        )
    try:
        docx_module = importlib.import_module('docx')
        enum_text_module = importlib.import_module('docx.enum.text')
        shared_module = importlib.import_module('docx.shared')
    except ImportError as exc:
        raise DocumentRendererUnavailable(
            capabilities['docx']['message'] or DOCX_BACKEND_UNAVAILABLE_MESSAGE
        ) from exc
    return docx_module, enum_text_module, shared_module


def _load_pdf_backend():
    capabilities = get_document_backend_capabilities()
    if not capabilities['pdf_available']:
        raise DocumentRendererUnavailable(
            capabilities['pdf']['message'] or PDF_BACKEND_UNAVAILABLE_MESSAGE
        )
    # Retorna o modulo docx2pdf se disponivel (pode nao ser necessario quando LibreOffice e usado).
    try:
        return importlib.import_module('docx2pdf')
    except ImportError:
        return None


def get_docx_backend_availability():
    return get_document_backend_capabilities()['docx']


def get_pdf_backend_availability():
    return get_document_backend_capabilities()['pdf']


def get_document_backend_availability(formato):
    formato = DocumentoFormato(formato)
    capabilities = get_document_backend_capabilities()
    if formato == DocumentoFormato.DOCX:
        return capabilities['docx']
    if formato == DocumentoFormato.PDF:
        return capabilities['pdf']
    return _build_availability(
        False,
        [f'Formato {formato.value.upper()} ainda não disponível nesta fase.'],
    )
