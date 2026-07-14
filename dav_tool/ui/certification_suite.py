"""Developer Mode — Certification Suite UI.

Embeddable in Streamlit developer mode panel.
Provides Run All / Run Category / Run Retailer controls
and generates HTML/Markdown reports.
"""
import streamlit as st

from dav_tool.certification.runner import (
    CertificationRunner, discover_retailer_datasets,
    CERTIFICATION_ROOT,
)


def render_certification_suite():
    """Render the Certification Suite in a Streamlit developer panel."""
    st.markdown("---")
    st.subheader("🧪 Certification Suite")

    datasets = discover_retailer_datasets()
    if not datasets:
        st.warning(f"No retailer datasets found under {CERTIFICATION_ROOT}")
        st.info("Run `python -m dav_tool.certification.datasets` to generate them.")
        return

    categories = sorted(set(c for c, _ in datasets))

    col1, col2, col3 = st.columns(3)

    with col1:
        run_all = st.button("▶️ Run All", use_container_width=True, type="primary")

    with col2:
        selected_category = st.selectbox("Category", [""] + categories, key="cert_cat")
        run_category = st.button("▶️ Run Category", use_container_width=True,
                                 disabled=not selected_category)

    with col3:
        retailer_options = [f"{c}/{r}" for c, r in datasets]
        selected_retailer = st.selectbox("Retailer", [""] + retailer_options, key="cert_ret")
        run_retailer = st.button("▶️ Run Retailer", use_container_width=True,
                                 disabled=not selected_retailer)

    runner = CertificationRunner()

    if run_all:
        with st.spinner("Running full certification suite..."):
            suite = runner.run_all()
            _display_suite_result(suite)
            _display_report_downloads(runner, suite)

    elif run_category and selected_category:
        with st.spinner(f"Running category: {selected_category}..."):
            suite = runner.run_category(selected_category)
            _display_suite_result(suite)
            _display_report_downloads(runner, suite)

    elif run_retailer and selected_retailer:
        cat, ret = selected_retailer.split("/", 1)
        with st.spinner(f"Running {cat}/{ret}..."):
            result = runner.run_one(cat, ret)
            _display_retailer_result(result, cat, ret)
            suite = runner.suite_result
            if suite.total > 0:
                _display_report_downloads(runner, suite)

    st.caption(f"Datasets: {len(datasets)} | Categories: {len(categories)}")


def _display_suite_result(suite):
    st.success(f"**Suite Result:** {suite.passed}/{suite.total} passed ({suite.duration:.2f}s)")
    for r in suite.results:
        status = "✅" if r.passed else "❌"
        st.markdown(f"{status} **{r.category}/{r.retailer}** — {r.duration:.2f}s")
        if not r.passed and r.errors:
            for err in r.errors[:5]:
                st.caption(f"  ↳ {err}")
            if len(r.errors) > 5:
                st.caption(f"  … and {len(r.errors) - 5} more errors")


def _display_retailer_result(result, category, retailer):
    status = "✅" if result.passed else "❌"
    st.markdown(f"### {status} {category}/{retailer}")
    st.markdown(f"**Duration:** {result.duration:.2f}s")
    st.markdown(f"**Discovery:** {'✓' if result.discovery_ok else '✗'}")
    st.markdown(f"**Config:** {'✓' if result.config_ok else '✗'}")
    st.markdown(f"**Processing:** {'✓' if result.processing_ok else '✗'}")
    st.markdown(f"**Validation:** {'✓' if result.validation_ok else '✗'}")
    st.markdown(f"**Expected Outputs Match:** {'✓' if result.expected_outputs_match else '—'}")

    if result.errors:
        st.error("Errors:")
        for err in result.errors:
            st.markdown(f"- {err}")

    if result.details:
        with st.expander("Details"):
            for k, v in result.details.items():
                st.markdown(f"**{k}:** {v}")


def _display_report_downloads(runner, suite):
    st.markdown("#### Download Reports")
    c1, c2, c3 = st.columns(3)
    with c1:
        md_report = runner.generate_report(suite, "markdown")
        st.download_button("Download Markdown Report", md_report,
                           file_name="certification_report.md", use_container_width=True)
    with c2:
        json_report = runner.generate_report(suite, "json")
        st.download_button("Download JSON Report", json_report,
                           file_name="certification_report.json", use_container_width=True)
    with c3:
        html_report = runner.generate_report(suite, "html")
        st.download_button("Download HTML Report", html_report,
                           file_name="certification_report.html", use_container_width=True)
