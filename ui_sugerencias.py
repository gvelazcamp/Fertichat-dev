# =========================
# ui_sugerencias.py - UI + CSS (CARDS CORPORATIVAS)
# =========================

import streamlit as st

CSS_SUGERENCIAS_PEDIDOS = """
<style>
/* =========================
   FERTICHAT · SUGERENCIAS (CORPORATIVO)
   ========================= */

:root{
    --fc-bg: #f6f8fb;
    --fc-card: #ffffff;
    --fc-border: rgba(15,23,42,0.10);
    --fc-text: #0f172a;
    --fc-muted: rgba(15,23,42,0.70);

    --fc-blue: #2563eb;
    --fc-blue-2: #1d4ed8;

    --fc-red: #ef4444;
    --fc-amber: #f59e0b;
    --fc-green: #22c55e;
    --fc-sky: #0ea5e9;
}

/* --- Container --- */
.main .block-container{
    max-width: 1180px;
    padding-top: 1.2rem;
    padding-bottom: 2.0rem;
}

/* --- Títulos --- */
.fc-title{
    font-size: 1.85rem;
    font-weight: 800;
    color: var(--fc-text);
    letter-spacing: -0.02em;
    margin: 0;
}
.fc-subtitle{
    font-size: 0.98rem;
    color: var(--fc-muted);
    margin: 0.25rem 0 1.0rem 0;
}
.fc-section-title{
    font-size: 1.15rem;
    font-weight: 800;
    color: var(--fc-text);
    margin: 0.6rem 0 0.6rem 0;
}

/* --- Divider --- */
.fc-divider{
    height: 1px;
    background: rgba(15,23,42,0.08);
    margin: 1rem 0;
    border-radius: 999px;
}

/* --- Cards base --- */
.fc-card{
    background: var(--fc-card);
    border: 1px solid var(--fc-border);
    border-radius: 16px;
    padding: 14px 14px;
    box-shadow: 0 10px 26px rgba(15,23,42,0.06);
}

/* --- Alert Grid --- */
.fc-alert-grid{
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 12px;
    align-items: stretch;
}
@media (max-width: 980px){
    .fc-alert-grid{ grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 520px){
    .fc-alert-grid{ grid-template-columns: 1fr; }
}

.fc-alert{
    border-radius: 16px;
    padding: 14px 14px;
    border: 1px solid var(--fc-border);
    box-shadow: 0 10px 26px rgba(15,23,42,0.06);
    background: var(--fc-card);
}
.fc-alert .t{
    font-size: 0.82rem;
    font-weight: 800;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: rgba(15,23,42,0.75);
    margin: 0 0 0.35rem 0;
}
.fc-alert .v{
    font-size: 1.65rem;
    font-weight: 900;
    color: var(--fc-text);
    margin: 0;
    letter-spacing: -0.02em;
}
.fc-alert .s{
    font-size: 0.92rem;
    color: rgba(15,23,42,0.70);
    margin-top: 0.25rem;
}

/* Estados */
.fc-urgente{
    background: linear-gradient(180deg, rgba(239,68,68,0.12) 0%, rgba(255,255,255,1) 60%);
    border-color: rgba(239,68,68,0.22);
}
.fc-proximo{
    background: linear-gradient(180deg, rgba(245,158,11,0.14) 0%, rgba(255,255,255,1) 60%);
    border-color: rgba(245,158,11,0.22);
}
.fc-planificar{
    background: linear-gradient(180deg, rgba(34,197,94,0.12) 0%, rgba(255,255,255,1) 60%);
    border-color: rgba(34,197,94,0.22);
}
.fc-saludable{
    background: linear-gradient(180deg, rgba(14,165,233,0.10) 0%, rgba(255,255,255,1) 60%);
    border-color: rgba(14,165,233,0.18);
}

/* --- Sugerencia Card --- */
.fc-sug-card{
    background: var(--fc-card);
    border: 1px solid var(--fc-border);
    border-radius: 18px;
    padding: 14px 14px;
    box-shadow: 0 12px 30px rgba(15,23,42,0.08);
    margin-bottom: 12px;
}
.fc-sug-top{
    display:flex;
    align-items:flex-start;
    justify-content:space-between;
    gap: 12px;
}
.fc-sug-title{
    font-size: 1.08rem;
    font-weight: 900;
    color: var(--fc-text);
    margin: 0;
    letter-spacing: -0.01em;
}
.fc-sug-sub{
    font-size: 0.92rem;
    color: rgba(15,23,42,0.74);
    margin: 0.25rem 0 0 0;
}
.fc-sug-meta{
    font-size: 0.86rem;
    color: rgba(15,23,42,0.62);
    margin-top: 0.25rem;
}

/* Badge */
.fc-badge{
    display:inline-flex;
    align-items:center;
    gap: 8px;
    padding: 7px 10px;
    border-radius: 999px;
    font-size: 0.80rem;
    font-weight: 900;
    border: 1px solid var(--fc-border);
    background: rgba(15,23,42,0.04);
    color: rgba(15,23,42,0.78);
    white-space: nowrap;
}
.fc-badge.urgente{ border-color: rgba(239,68,68,0.22); background: rgba(239,68,68,0.12); }
.fc-badge.proximo{ border-color: rgba(245,158,11,0.22); background: rgba(245,158,11,0.14); }
.fc-badge.planificar{ border-color: rgba(34,197,94,0.22); background: rgba(34,197,94,0.12); }
.fc-badge.saludable{ border-color: rgba(14,165,233,0.18); background: rgba(14,165,233,0.10); }

/* Barra estado */
.fc-statusbar{
    margin-top: 10px;
    border-radius: 12px;
    padding: 10px 12px;
    border: 1px solid rgba(15,23,42,0.08);
}
.fc-statusbar.urgente{ background: rgba(239,68,68,0.10); }
.fc-statusbar.proximo{ background: rgba(245,158,11,0.12); }
.fc-statusbar.planificar{ background: rgba(34,197,94,0.10); }
.fc-statusbar.saludable{ background: rgba(14,165,233,0.08); }

.fc-statusbar .label{
    font-size: 0.86rem;
    font-weight: 900;
    color: rgba(15,23,42,0.85);
}

/* Métricas dentro de la card */
.fc-sug-grid{
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
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
    border-radius: 14px;
    padding: 10px 10px;
    background: rgba(15,23,42,0.02);
}
.fc-metric .k{
    font-size: 0.78rem;
    color: rgba(15,23,42,0.68);
    margin: 0;
    font-weight: 800;
}
.fc-metric .v{
    font-size: 1.12rem;
    font-weight: 900;
    color: var(--fc-text);
    margin: 0.20rem 0 0 0;
    letter-spacing: -0.01em;
}

/* Botones fake dentro de la card (solo visual) */
.fc-actions-row{
    display:flex;
    gap: 10px;
    margin-top: 12px;
    flex-wrap: wrap;
}
.fc-btn{
    display:inline-flex;
    align-items:center;
    justify-content:center;
    padding: 9px 12px;
    border-radius: 12px;
    border: 1px solid rgba(15,23,42,0.10);
    background: rgba(15,23,42,0.02);
    font-weight: 900;
    font-size: 0.88rem;
    color: rgba(15,23,42,0.82);
}
.fc-btn.primary{
    background: linear-gradient(180deg, var(--fc-blue) 0%, var(--fc-blue-2) 100%);
    color: #fff;
    border-color: rgba(37,99,235,0.45);
}

/* Inputs */
label{
    color: rgba(15,23,42,0.72) !important;
    font-weight: 700 !important;
}
div[data-testid="stSelectbox"] > div,
div[data-testid="stTextInput"] > div{
    border-radius: 12px;
}

/* Ocultar alerts nativos de Streamlit dentro de sugerencias */
.fc-sug-card div[data-testid="stAlert"]{
    display: none !important;
}

/* Separación clara entre título de sección y primer card */
.fc-section-title{
    margin-bottom: 1rem !important;
}
</style>
"""

def render_title(titulo: str, subtitulo: str):
    st.markdown(f'<div class="fc-title">{titulo}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="fc-subtitle">{subtitulo}</div>', unsafe_allow_html=True)

def render_section_title(titulo: str):
    st.markdown(f'<div class="fc-section-title">{titulo}</div>', unsafe_allow_html=True)

def render_divider():
    st.markdown('<div class="fc-divider"></div>', unsafe_allow_html=True)

def render_card(html: str, extra_class: str = ""):
    cls = "fc-card"
    if extra_class:
        cls = f"{cls} {extra_class}"
    st.markdown(f'<div class="{cls}">{html}</div>', unsafe_allow_html=True)

def render_alert_grid(alerts: list):
    # ✅ IMPORTANTE: TODO el HTML en UNA sola llamada, si no Streamlit lo rompe y se apila.
    parts = ['<div class="fc-alert-grid">']
    for a in alerts:
        title = str(a.get("title", ""))
        value = str(a.get("value", ""))
        subtitle = str(a.get("subtitle", ""))
        css_class = str(a.get("class", "")).strip()
        parts.append(
            f"""
            <div class="fc-alert {css_class}">
                <div class="t">{title}</div>
                <div class="v">{value}</div>
                <div class="s">{subtitle}</div>
            </div>
            """
        )
    parts.append("</div>")
    st.markdown("\n".join(parts), unsafe_allow_html=True)

def render_sugerencia_card(
    producto: str,
    proveedor: str,
    ultima_compra: str,
    urgencia: str,
    compras_anuales: float,
    compras_mensuales: float,
    compra_sugerida: float,
    stock_actual: float,
    unidad: str
):
    urg = (urgencia or "saludable").strip().lower()

    badge_map = {
        "urgente": "URGENTE",
        "proximo": "PRÓXIMAMENTE",
        "planificar": "PLANIFICAR",
        "saludable": "STOCK SALUDABLE",
    }
    badge_text = badge_map.get(urg, "STOCK SALUDABLE")

    st.markdown('<div class="fc-sug-card">', unsafe_allow_html=True)

    st.markdown(
        f"""
        <div class="fc-sug-top">
            <div>
                <div class="fc-sug-title">{producto}</div>
                <div class="fc-sug-sub">Proveedor: <strong>{proveedor}</strong></div>
                <div class="fc-sug-meta">Última compra: {ultima_compra}</div>
            </div>
            <div class="fc-badge {urg}">{badge_text}</div>
        </div>

        <div class="fc-statusbar {urg}">
            <span class="label">{badge_text}</span>
        </div>

        <div class="fc-sug-grid">
            <div class="fc-metric">
                <div class="k">Compras anuales</div>
                <div class="v">{compras_anuales:g} {unidad}</div>
            </div>
            <div class="fc-metric">
                <div class="k">Compras mensuales</div>
                <div class="v">{compras_mensuales:g} {unidad}</div>
            </div>
            <div class="fc-metric">
                <div class="k">Compra sugerida</div>
                <div class="v">{compra_sugerida:g} {unidad}</div>
            </div>
            <div class="fc-metric">
                <div class="k">Stock actual</div>
                <div class="v">{stock_actual:g} {unidad}</div>
            </div>
        </div>

        <div class="fc-actions-row">
            <span class="fc-btn primary">Generar orden</span>
            <span class="fc-btn">Ajustar cantidad</span>
            <span class="fc-btn">Ver historial</span>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.markdown('</div>', unsafe_allow_html=True)

def render_actions():
    pass
