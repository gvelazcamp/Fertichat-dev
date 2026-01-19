# =========================
# UI_SUGERENCIAS.PY - ESTILOS Y HELPERS UI PARA SUGERENCIAS DE PEDIDOS
# =========================

import streamlit as st

# =========================
# CSS PARA SUGERENCIAS DE PEDIDOS
# =========================
CSS_SUGERENCIAS_PEDIDOS = """
<style>
/* =========================
   FERTICHAT · SUGERENCIAS (CORPORATIVO)
   SOLO CSS (Streamlit)
   ========================= */

/* --- Layout base Streamlit --- */
.main .block-container{
    padding-top: 1.2rem;
    padding-bottom: 2.2rem;
    max-width: 1180px;
}
section[data-testid="stSidebar"]{
    border-right: 1px solid rgba(15,23,42,0.08);
    background: #ffffff;
}

/* --- Tipografía y títulos --- */
.fc-title{
    font-size: 1.55rem;
    font-weight: 700;
    letter-spacing: -0.02em;
    margin: 0;
    color: #0f172a;
}
.fc-subtitle{
    font-size: 0.95rem;
    color: rgba(15,23,42,0.72);
    margin-top: 0.35rem;
    margin-bottom: 0.75rem;
}
.fc-section-title{
    font-size: 1.05rem;
    font-weight: 700;
    color: #0f172a;
    margin: 0 0 0.6rem 0;
}

/* --- Cards generales --- */
.fc-card{
    background: #ffffff;
    border: 1px solid rgba(15,23,42,0.10);
    border-radius: 14px;
    padding: 14px 14px;
    box-shadow: 0 8px 22px rgba(15,23,42,0.06);
}
.fc-card + .fc-card{ margin-top: 0.75rem; }

/* --- Card info (análisis) --- */
.fc-info{
    border-left: 6px solid rgba(37,99,235,0.85);
    background: linear-gradient(180deg, rgba(37,99,235,0.06) 0%, rgba(255,255,255,1) 55%);
}
.fc-info p{
    margin: 0.2rem 0;
    color: rgba(15,23,42,0.78);
    font-size: 0.93rem;
}
.fc-info strong{
    color: #0f172a;
}

/* --- Grid para Alertas (4 cards) --- */
.fc-alert-grid{
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 12px;
}
@media (max-width: 980px){
    .fc-alert-grid{ grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 520px){
    .fc-alert-grid{ grid-template-columns: 1fr; }
}

.fc-alert{
    border-radius: 14px;
    padding: 14px 14px;
    border: 1px solid rgba(15,23,42,0.10);
    box-shadow: 0 8px 22px rgba(15,23,42,0.06);
    color: #0f172a;
    background: #ffffff;
}
.fc-alert .k{
    font-size: 0.80rem;
    font-weight: 700;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    margin: 0;
    display: flex;
    align-items: center;
    gap: 8px;
}
.fc-alert .v{
    font-size: 1.55rem;
    font-weight: 800;
    margin: 0.15rem 0 0 0;
    letter-spacing: -0.02em;
}
.fc-alert .s{
    font-size: 0.90rem;
    color: rgba(15,23,42,0.75);
    margin-top: 0.15rem;
}

/* Variantes de color (sin neon, corporativo) */
.fc-urgente{
    background: linear-gradient(180deg, rgba(239,68,68,0.10) 0%, rgba(255,255,255,1) 55%);
    border-color: rgba(239,68,68,0.22);
}
.fc-proximo{
    background: linear-gradient(180deg, rgba(245,158,11,0.12) 0%, rgba(255,255,255,1) 55%);
    border-color: rgba(245,158,11,0.22);
}
.fc-planificar{
    background: linear-gradient(180deg, rgba(34,197,94,0.10) 0%, rgba(255,255,255,1) 55%);
    border-color: rgba(34,197,94,0.22);
}
.fc-saludable{
    background: linear-gradient(180deg, rgba(37,99,235,0.08) 0%, rgba(255,255,255,1) 55%);
    border-color: rgba(37,99,235,0.18);
}

/* --- Panel de filtros tipo card --- */
.fc-filters{
    background: #ffffff;
    border: 1px solid rgba(15,23,42,0.10);
    border-radius: 14px;
    padding: 12px 12px;
    box-shadow: 0 8px 22px rgba(15,23,42,0.06);
}
.fc-filters .label{
    font-size: 0.78rem;
    font-weight: 700;
    color: rgba(15,23,42,0.70);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 0.3rem;
}

/* --- Cards de sugerencias (listado) --- */
.fc-sug-card{
    background: #ffffff;
    border: 1px solid rgba(15,23,42,0.10);
    border-radius: 16px;
    padding: 14px 14px;
    box-shadow: 0 10px 26px rgba(15,23,42,0.07);
}
.fc-sug-top{
    display:flex;
    align-items:flex-start;
    justify-content:space-between;
    gap: 12px;
}
.fc-sug-title{
    font-size: 1.05rem;
    font-weight: 800;
    margin: 0;
    color: #0f172a;
    letter-spacing: -0.01em;
}
.fc-sug-sub{
    font-size: 0.90rem;
    color: rgba(15,23,42,0.75);
    margin: 0.2rem 0 0 0;
}
.fc-badge{
    display:inline-flex;
    align-items:center;
    gap: 6px;
    padding: 6px 10px;
    border-radius: 999px;
    font-size: 0.80rem;
    font-weight: 700;
    border: 1px solid rgba(15,23,42,0.10);
    background: rgba(15,23,42,0.04);
    color: rgba(15,23,42,0.78);
    white-space: nowrap;
}
.fc-badge.urgente{ border-color: rgba(239,68,68,0.22); background: rgba(239,68,68,0.10); }
.fc-badge.proximo{ border-color: rgba(245,158,11,0.22); background: rgba(245,158,11,0.12); }
.fc-badge.planificar{ border-color: rgba(34,197,94,0.22); background: rgba(34,197,94,0.10); }
.fc-badge.saludable{ border-color: rgba(37,99,235,0.18); background: rgba(37,99,235,0.10); }

.fc-sug-grid{
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 10px;
    margin-top: 12px;
}
@media (max-width: 980px){
    .fc-sug-grid{ grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 520px){
    .fc-sug-grid{ grid-template-columns: 1fr; }
}
.fc-metric{
    border: 1px solid rgba(15,23,42,0.08);
    border-radius: 12px;
    padding: 10px 10px;
    background: rgba(15,23,42,0.02);
}
.fc-metric .k{
    font-size: 0.78rem;
    color: rgba(15,23,42,0.68);
    margin: 0;
}
.fc-metric .v{
    font-size: 1.02rem;
    font-weight: 800;
    color: #0f172a;
    margin: 0.18rem 0 0 0;
}

/* --- Barra de acciones (botones) --- */
.fc-actions{
    display:flex;
    flex-wrap: wrap;
    gap: 10px;
    align-items:center;
    margin-top: 12px;
}

/* Streamlit buttons inside container */
.fc-actions div[data-testid="stButton"] button,
.fc-primary div[data-testid="stButton"] button{
    border-radius: 12px !important;
    padding: 0.55rem 0.85rem !important;
    font-weight: 700 !important;
    border: 1px solid rgba(15,23,42,0.12) !important;
    box-shadow: 0 8px 18px rgba(15,23,42,0.08) !important;
}
.fc-primary div[data-testid="stButton"] button{
    background: linear-gradient(180deg, rgba(37,99,235,1) 0%, rgba(29,78,216,1) 100%) !important;
    color: #ffffff !important;
    border-color: rgba(37,99,235,0.55) !important;
}
.fc-actions div[data-testid="stButton"] button:hover,
.fc-primary div[data-testid="stButton"] button:hover{
    filter: brightness(0.98);
    transform: translateY(-1px);
}

/* --- Tabla/df (si usás st.dataframe) --- */
div[data-testid="stDataFrame"]{
    border: 1px solid rgba(15,23,42,0.10);
    border-radius: 14px;
    overflow: hidden;
    box-shadow: 0 10px 26px rgba(15,23,42,0.07);
}

/* --- Inputs/Selects más pro --- */
div[data-testid="stSelectbox"] > div,
div[data-testid="stTextInput"] > div,
div[data-testid="stNumberInput"] > div{
    border-radius: 12px;
}
label{
    color: rgba(15,23,42,0.72) !important;
    font-weight: 600 !important;
}

/* --- Separadores suaves --- */
.fc-divider{
    height: 1px;
    background: rgba(15,23,42,0.08);
    margin: 0.9rem 0;
    border-radius: 999px;
}
</style>
"""

# =========================
# FUNCIONES HELPERS UI
# =========================

def apply_css_sugerencias():
    """
    Aplica los estilos CSS para la página de sugerencias de pedidos.
    """
    st.markdown(CSS_SUGERENCIAS_PEDIDOS, unsafe_allow_html=True)

def render_title(title: str, subtitle: str = None):
    """
    Renderiza un título con subtítulo opcional usando clases CSS.
    """
    st.markdown(f'<h1 class="fc-title">{title}</h1>', unsafe_allow_html=True)
    if subtitle:
        st.markdown(f'<p class="fc-subtitle">{subtitle}</p>', unsafe_allow_html=True)

def render_section_title(title: str):
    """
    Renderiza un título de sección.
    """
    st.markdown(f'<h2 class="fc-section-title">{title}</h2>', unsafe_allow_html=True)

def render_card(content: str, class_name: str = "fc-card"):
    """
    Renderiza una card con contenido HTML.
    """
    st.markdown(f'<div class="{class_name}">{content}</div>', unsafe_allow_html=True)

def render_alert_grid(alerts: list):
    """
    Renderiza una grid de alertas. Cada alerta es un dict con 'title', 'value', 'subtitle', 'class'.
    """
    html = '<div class="fc-alert-grid">'
    for alert in alerts:
        html += f'''
        <div class="fc-alert {alert.get('class', '')}">
            <p class="k">{alert['title']}</p>
            <p class="v">{alert['value']}</p>
            <p class="s">{alert['subtitle']}</p>
        </div>
        '''
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)

def render_sugerencia_card(title: str, subtitle: str, badge: str, badge_class: str, metrics: list):
    """
    Renderiza una card de sugerencia con métricas.
    """
    metrics_html = '<div class="fc-sug-grid">'
    for metric in metrics:
        metrics_html += f'''
        <div class="fc-metric">
            <p class="k">{metric['key']}</p>
            <p class="v">{metric['value']}</p>
        </div>
        '''
    metrics_html += '</div>'

    html = f'''
    <div class="fc-sug-card">
        <div class="fc-sug-top">
            <div>
                <h3 class="fc-sug-title">{title}</h3>
                <p class="fc-sug-sub">{subtitle}</p>
            </div>
            <span class="fc-badge {badge_class}">{badge}</span>
        </div>
        {metrics_html}
    </div>
    '''
    st.markdown(html, unsafe_allow_html=True)

def render_actions(buttons: list):
    """
    Renderiza una barra de acciones con botones. Cada botón es un dict con 'label', 'key', 'primary'.
    """
    html = '<div class="fc-actions">'
    for btn in buttons:
        class_name = "fc-primary" if btn.get('primary', False) else ""
        html += f'<div class="{class_name}">{st.button(btn["label"], key=btn["key"])}</div>'
    html += '</div>'
    # Nota: st.button dentro de markdown no funciona bien, usar st.columns en lugar.

# Para botones, mejor usar st.columns con st.button directamente, pero como helper, sugerir estructura.

def render_divider():
    """
    Renderiza un separador suave.
    """
    st.markdown('<div class="fc-divider"></div>', unsafe_allow_html=True)