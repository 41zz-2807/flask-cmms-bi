QUERIES = {
    "asset_wo_frequency": {
        "title": "Aset Paling Sering Meminta WO",
        "type": "bar",
        "sql": """
            SELECT pr.name AS x, COUNT(wo.om_wo_id) AS y
            FROM om_wo wo
            INNER JOIN om_product pr ON wo.asset_id = pr.om_product_id
            WHERE wo.created_date BETWEEN %(start_date)s AND %(end_date)s
              AND wo.asset_id IS NOT NULL
              AND (%(m_org_ids)s IS NULL OR wo.m_org_id = ANY(%(m_org_ids)s))
            GROUP BY pr.name
            ORDER BY y DESC
            LIMIT 10;
        """,
    },
    "pm_compliance": {
        "title": "Kepatuhan Jadwal Rutin (Preventive Maintenance)",
        "type": "pie",
        "sql": """
            SELECT COALESCE(doc_status, 'UNKNOWN') AS x, COUNT(om_wo_id) AS y
            FROM om_wo
            WHERE type ILIKE 'SCH'
              AND created_date BETWEEN %(start_date)s AND %(end_date)s
              AND (%(m_org_ids)s IS NULL OR m_org_id = ANY(%(m_org_ids)s))
            GROUP BY doc_status;
        """,
    },
    "sparepart_fast_moving": {
        "title": "Sparepart Fast Moving",
        "type": "bar",
        "sql": """
            SELECT pr.name AS x, SUM(wi.qty) AS y
            FROM om_wo_item wi
            JOIN om_wo w ON wi.om_wo_id = w.om_wo_id
            INNER JOIN om_product pr ON wi.om_product_id = pr.om_product_id
            WHERE w.created_date BETWEEN %(start_date)s AND %(end_date)s
              AND (%(m_org_ids)s IS NULL OR w.m_org_id = ANY(%(m_org_ids)s))
            GROUP BY pr.name
            ORDER BY y DESC
            LIMIT 10;
        """,
    },
    "technician_performance": {
        "title": "Kinerja Teknisi (Beban Kerja WO)",
        "type": "bar",
        "sql": """
            SELECT u.name AS x, COUNT(w.om_wo_id) AS y
            FROM om_wo w
            INNER JOIN om_wo_appr appr ON w.om_wo_id = appr.om_wo_id
            INNER JOIN om_wo_appr_history apprh ON appr.om_wo_appr_id = apprh.om_wo_appr_id
            INNER JOIN m_user u ON apprh.last_approved = u.m_user_id
            WHERE apprh.last_approval IN (3, 4)
              AND w.created_date BETWEEN %(start_date)s AND %(end_date)s
              AND (%(m_org_ids)s IS NULL OR w.m_org_id = ANY(%(m_org_ids)s))
            GROUP BY u.name
            ORDER BY y DESC
            LIMIT 10;
        """,
    },
    "biaya_wo": {
        "title": "Work Order dengan Biaya Tertinggi (Budget)",
        "type": "bar",
        "sql": """
            SELECT w.value AS x, w.budget AS y
            FROM om_wo w
            WHERE w.budget IS NOT NULL
              AND w.created_date BETWEEN %(start_date)s AND %(end_date)s
              AND (%(m_org_ids)s IS NULL OR w.m_org_id = ANY(%(m_org_ids)s))
            ORDER BY y DESC
            LIMIT 10;
        """,
    },
    "asset_wo_summary": {
        "title": "Rekapitulasi WO per Aset (SCH & REQ)",
        "type": "none",
        "sql": "SELECT 1 AS x, 0 AS y LIMIT 0;",
    },
    "kpi_site": {
        "title": "KPI per Site",
        "type": "bar",
        "sql": """
            SELECT o.name AS x, COUNT(wo.om_wo_id) AS y
            FROM om_wo wo
            INNER JOIN m_org o ON wo.m_org_id = o.m_org_id
            WHERE wo.created_date BETWEEN %(start_date)s AND %(end_date)s
              AND (%(m_org_ids)s IS NULL OR wo.m_org_id = ANY(%(m_org_ids)s))
            GROUP BY o.m_org_id, o.name
            ORDER BY y DESC;
        """,
    },
    "wo_request": {
        "title": "Daftar Request (WO Ber-REQ)",
        "type": "none",
        "sql": "SELECT 1 AS x, 0 AS y LIMIT 0;",
    },
    "wo_durasi_proses": {
        "title": "Durasi Proses WO (Creation → Approval → Close)",
        "type": "none",
        "sql": "SELECT 1 AS x, 0 AS y LIMIT 0;",
    },
    "tren_bulanan": {
        "title": "Tren & Musiman WO Bulanan",
        "type": "line",
        "sql": "SELECT 1 AS x, 0 AS y LIMIT 0;",
    },
    "pareto_sparepart": {
        "title": "Pareto (ABC) Sparepart",
        "type": "pareto",
        "sql": "SELECT 1 AS x, 0 AS y LIMIT 0;",
    },
    "mtbf_mttr": {
        "title": "MTBF / MTTR per Aset",
        "type": "mtbf_mttr",
        "sql": "SELECT 1 AS x, 0 AS y LIMIT 0;",
    },
    "profil_teknisi": {
        "title": "Profil Teknisi (Workload, Durasi, Backlog)",
        "type": "teknisi",
        "sql": "SELECT 1 AS x, 0 AS y LIMIT 0;",
    },
    "data_quality": {
        "title": "Data Quality Report",
        "type": "bar",
        "sql": "SELECT 1 AS x, 0 AS y LIMIT 0;",
    },
}

TABLE_SQL = {
    "asset_wo_frequency": """
        SELECT DISTINCT w.om_wo_id AS wo_id, w.value AS no_wo, w.description, w.doc_status AS status,
               w.created_date AS tanggal, pr.name AS aset
        FROM om_wo w
        INNER JOIN om_product pr ON w.asset_id = pr.om_product_id
        INNER JOIN (
            SELECT pr_in.om_product_id AS pid
            FROM om_wo wo_in
            INNER JOIN om_product pr_in ON wo_in.asset_id = pr_in.om_product_id
            WHERE wo_in.created_date BETWEEN %(start_date)s AND %(end_date)s
              AND wo_in.asset_id IS NOT NULL
              AND (%(m_org_ids)s IS NULL OR wo_in.m_org_id = ANY(%(m_org_ids)s))
            GROUP BY pr_in.om_product_id
            ORDER BY COUNT(wo_in.om_wo_id) DESC
            LIMIT 10
        ) top ON top.pid = pr.om_product_id
        WHERE w.created_date BETWEEN %(start_date)s AND %(end_date)s
          AND (%(m_org_ids)s IS NULL OR w.m_org_id = ANY(%(m_org_ids)s))
        ORDER BY w.created_date DESC
    """,
    "pm_compliance": """
        SELECT DISTINCT w.om_wo_id AS wo_id, w.value AS no_wo, w.description, w.doc_status AS status,
               w.created_date AS tanggal, w.type AS tipe
        FROM om_wo w
        WHERE w.type ILIKE 'SCH'
          AND w.created_date BETWEEN %(start_date)s AND %(end_date)s
          AND (%(m_org_ids)s IS NULL OR w.m_org_id = ANY(%(m_org_ids)s))
        ORDER BY w.created_date DESC
    """,
    "sparepart_fast_moving": """
        WITH top AS (
            SELECT pr_in.om_product_id AS pid
            FROM om_wo_item wi_in
            JOIN om_wo wo_in ON wi_in.om_wo_id = wo_in.om_wo_id
            INNER JOIN om_product pr_in ON wi_in.om_product_id = pr_in.om_product_id
            WHERE wo_in.created_date BETWEEN %(start_date)s AND %(end_date)s
              AND (%(m_org_ids)s IS NULL OR wo_in.m_org_id = ANY(%(m_org_ids)s))
            GROUP BY pr_in.om_product_id
            ORDER BY SUM(wi_in.qty) DESC
            LIMIT 10
        ),
        latest AS (
            SELECT DISTINCT ON (pr_in.om_product_id)
                   pr_in.om_product_id AS pid,
                   w_in.created_date AS tanggal,
                   w_in.doc_status AS status
            FROM om_wo_item wi_in
            JOIN om_wo w_in ON wi_in.om_wo_id = w_in.om_wo_id
            INNER JOIN om_product pr_in ON wi_in.om_product_id = pr_in.om_product_id
            INNER JOIN top ON top.pid = pr_in.om_product_id
            WHERE w_in.created_date BETWEEN %(start_date)s AND %(end_date)s
              AND (%(m_org_ids)s IS NULL OR w_in.m_org_id = ANY(%(m_org_ids)s))
            ORDER BY pr_in.om_product_id, w_in.created_date DESC
        )
        SELECT pr.name AS sparepart,
               COUNT(DISTINCT w.om_wo_id) AS jmlwo,
               lt.tanggal AS tanggal,
               lt.status AS status
        FROM om_wo_item wi
        JOIN om_wo w ON wi.om_wo_id = w.om_wo_id
        INNER JOIN om_product pr ON wi.om_product_id = pr.om_product_id
        INNER JOIN top ON top.pid = pr.om_product_id
        INNER JOIN latest lt ON lt.pid = pr.om_product_id
        WHERE w.created_date BETWEEN %(start_date)s AND %(end_date)s
          AND (%(m_org_ids)s IS NULL OR w.m_org_id = ANY(%(m_org_ids)s))
        GROUP BY pr.name, lt.tanggal, lt.status
        ORDER BY jmlwo DESC
    """,
    "technician_performance": """
        SELECT DISTINCT w.om_wo_id AS wo_id, w.value AS no_wo, w.description, w.doc_status AS status,
               w.created_date AS tanggal, u.name AS teknisi,
               CASE WHEN dur.start_ts IS NOT NULL AND dur.end_ts IS NOT NULL
                    THEN EXTRACT(EPOCH FROM (dur.end_ts - dur.start_ts))::int
                    ELSE NULL END AS durasi
        FROM om_wo w
        INNER JOIN om_wo_appr appr ON w.om_wo_id = appr.om_wo_id
        INNER JOIN om_wo_appr_history apprh ON appr.om_wo_appr_id = apprh.om_wo_appr_id
        INNER JOIN m_user u ON apprh.last_approved = u.m_user_id
        INNER JOIN (
            SELECT a2.om_wo_id AS wid, h2.last_approved AS uid,
                   MIN(h2.created_date) AS start_ts,
                   MAX(h2.created_date) FILTER (WHERE h2.last_status IN ('CO','CL')) AS end_ts
            FROM om_wo_appr a2
            INNER JOIN om_wo_appr_history h2 ON a2.om_wo_appr_id = h2.om_wo_appr_id
            WHERE h2.last_approved IS NOT NULL
            GROUP BY a2.om_wo_id, h2.last_approved
        ) dur ON dur.wid = w.om_wo_id AND dur.uid = u.m_user_id
        INNER JOIN (
            SELECT u_in.m_user_id AS uid
            FROM om_wo wo_in
            INNER JOIN om_wo_appr appr_in ON wo_in.om_wo_id = appr_in.om_wo_id
            INNER JOIN om_wo_appr_history apprh_in ON appr_in.om_wo_appr_id = apprh_in.om_wo_appr_id
            INNER JOIN m_user u_in ON apprh_in.last_approved = u_in.m_user_id
            WHERE apprh_in.last_approval IN (3, 4)
              AND wo_in.created_date BETWEEN %(start_date)s AND %(end_date)s
              AND (%(m_org_ids)s IS NULL OR wo_in.m_org_id = ANY(%(m_org_ids)s))
            GROUP BY u_in.m_user_id
            ORDER BY COUNT(wo_in.om_wo_id) DESC
            LIMIT 10
        ) top ON top.uid = u.m_user_id
        WHERE apprh.last_approval IN (3, 4)
          AND w.created_date BETWEEN %(start_date)s AND %(end_date)s
          AND (%(m_org_ids)s IS NULL OR w.m_org_id = ANY(%(m_org_ids)s))
        ORDER BY w.created_date DESC
    """,
    "biaya_wo": """
        SELECT DISTINCT w.om_wo_id AS wo_id, w.value AS no_wo, w.description, w.doc_status AS status,
               w.created_date AS tanggal, w.budget
        FROM om_wo w
        WHERE w.budget IS NOT NULL
          AND w.created_date BETWEEN %(start_date)s AND %(end_date)s
          AND (%(m_org_ids)s IS NULL OR w.m_org_id = ANY(%(m_org_ids)s))
        ORDER BY w.budget DESC
    """,
    "asset_wo_summary": """
        WITH per AS (
            SELECT COALESCE(pr.name, 'Tanpa Aset') AS aset,
                   COUNT(*) FILTER (WHERE w.type ILIKE 'SCH') AS sch_total,
                   COUNT(*) FILTER (WHERE w.type ILIKE 'REQ') AS req_total
            FROM om_wo w
            LEFT JOIN om_product pr ON w.asset_id = pr.om_product_id
            WHERE w.type ILIKE ANY ('{SCH,REQ}')
              AND w.created_date BETWEEN %(start_date)s AND %(end_date)s
              AND (%(m_org_ids)s IS NULL OR w.m_org_id = ANY(%(m_org_ids)s))
            GROUP BY COALESCE(pr.name, 'Tanpa Aset')
        ),
        latest AS (
            SELECT aset, status, tanggal FROM (
                SELECT COALESCE(pr.name, 'Tanpa Aset') AS aset,
                       w.doc_status AS status,
                       w.created_date AS tanggal,
                       ROW_NUMBER() OVER (PARTITION BY COALESCE(pr.name, 'Tanpa Aset')
                                          ORDER BY w.created_date DESC) AS rn
                FROM om_wo w
                LEFT JOIN om_product pr ON w.asset_id = pr.om_product_id
                WHERE w.type ILIKE ANY ('{SCH,REQ}')
                  AND w.created_date BETWEEN %(start_date)s AND %(end_date)s
                  AND (%(m_org_ids)s IS NULL OR w.m_org_id = ANY(%(m_org_ids)s))
            ) x
            WHERE rn = 1
        )
        SELECT p.aset, p.sch_total, p.req_total, lt.status, lt.tanggal
        FROM per p
        LEFT JOIN latest lt USING (aset)
        ORDER BY p.aset
    """,
    "wo_request": """
        SELECT w.om_wo_id AS wo_id, w.value AS no_wo, w.doc_status AS status,
               COALESCE(h.last_status, w.doc_status) AS status_workflow,
               w.created_date AS created_date, w.closed_date AS closed_date,
               w.description
        FROM om_wo w
        LEFT JOIN LATERAL (
            SELECT apprh.last_status
            FROM om_wo_appr appr
            INNER JOIN om_wo_appr_history apprh ON appr.om_wo_appr_id = apprh.om_wo_appr_id
            WHERE appr.om_wo_id = w.om_wo_id
            ORDER BY apprh.created_date DESC, apprh.om_wo_appr_history_id DESC
            LIMIT 1
        ) h ON TRUE
        WHERE w.value ILIKE '%%REQ%%'
          AND w.created_date BETWEEN %(start_date)s AND %(end_date)s
          AND (%(m_org_ids)s IS NULL OR w.m_org_id = ANY(%(m_org_ids)s))
        ORDER BY w.created_date DESC
    """,
    "wo_durasi_proses": """
        WITH latest_appr AS (
            SELECT DISTINCT ON (appr.om_wo_id) appr.om_wo_id, appr.om_wo_appr_id
            FROM om_wo_appr appr
            ORDER BY appr.om_wo_id, appr.created_date DESC, appr.om_wo_appr_id DESC
        ),
        hist AS (
            SELECT la.om_wo_id,
                   MIN(h.created_date) AS submit_ts,
                   MIN(h.created_date) FILTER (WHERE h.last_status = 'CO') AS co_ts,
                   MIN(h.created_date) FILTER (WHERE h.last_status = 'CL') AS cl_ts,
                   COUNT(*) FILTER (
                       WHERE h.last_approved IS NOT NULL
                         AND h.last_approved <> 999999999
                         AND h.last_approval IS NOT NULL
                   ) AS jml_approval
            FROM latest_appr la
            INNER JOIN om_wo_appr_history h ON h.om_wo_appr_id = la.om_wo_appr_id
            GROUP BY la.om_wo_id
        )
        SELECT w.om_wo_id AS wo_id, w.value AS no_wo, w.doc_status AS status, w.type AS tipe,
               o.name AS site,
               w.created_date AS created_date, w.closed_date AS closed_date,
               ROUND(EXTRACT(EPOCH FROM (w.closed_date - w.created_date)) / 3600.0, 1) AS durasi_total_jam,
               ROUND(EXTRACT(EPOCH FROM (h.co_ts - h.submit_ts)) / 3600.0, 1) AS durasi_approval_jam,
               ROUND(EXTRACT(EPOCH FROM (h.cl_ts - h.co_ts)) / 3600.0, 1) AS durasi_exec_jam,
               h.jml_approval
        FROM om_wo w
        LEFT JOIN hist h USING (om_wo_id)
        LEFT JOIN m_org o ON w.m_org_id = o.m_org_id
        WHERE w.doc_status = 'CL'
          AND w.created_date BETWEEN %(start_date)s AND %(end_date)s
          AND (%(m_org_ids)s IS NULL OR w.m_org_id = ANY(%(m_org_ids)s))
        ORDER BY w.created_date DESC
    """,
}

SUMMARY_SQL = {
    "asset_wo_frequency": """
        WITH top AS (
            SELECT pr_in.om_product_id AS pid
            FROM om_wo wo_in
            INNER JOIN om_product pr_in ON wo_in.asset_id = pr_in.om_product_id
            WHERE wo_in.created_date BETWEEN %(start_date)s AND %(end_date)s
              AND wo_in.asset_id IS NOT NULL
              AND (%(m_org_ids)s IS NULL OR wo_in.m_org_id = ANY(%(m_org_ids)s))
            GROUP BY pr_in.om_product_id
            ORDER BY COUNT(wo_in.om_wo_id) DESC
            LIMIT 10
        ),
        per AS (
            SELECT pr.name, COUNT(DISTINCT w.om_wo_id) AS cnt
            FROM om_wo w
            INNER JOIN om_product pr ON w.asset_id = pr.om_product_id
            INNER JOIN top ON top.pid = pr.om_product_id
            WHERE w.created_date BETWEEN %(start_date)s AND %(end_date)s
              AND (%(m_org_ids)s IS NULL OR w.m_org_id = ANY(%(m_org_ids)s))
            GROUP BY pr.name
        )
        SELECT COUNT(*) AS tot_aset,
               SUM(cnt) AS tot_wo,
               MAX(cnt) AS top_cnt
        FROM per
    """,
    "pm_compliance": """
        SELECT COUNT(*) AS total,
               COUNT(*) FILTER (WHERE doc_status = 'CL') AS closed,
               COUNT(*) FILTER (WHERE doc_status IN ('CO', 'RE', 'IP')) AS open,
               ROUND(COUNT(*) FILTER (WHERE doc_status = 'CL') * 100.0 / NULLIF(COUNT(*), 0), 1) AS pct_closed
        FROM om_wo
        WHERE type ILIKE 'SCH'
          AND created_date BETWEEN %(start_date)s AND %(end_date)s
          AND (%(m_org_ids)s IS NULL OR m_org_id = ANY(%(m_org_ids)s))
    """,
    "sparepart_fast_moving": """
        WITH top AS (
            SELECT pr_in.om_product_id AS pid
            FROM om_wo_item wi_in
            JOIN om_wo wo_in ON wi_in.om_wo_id = wo_in.om_wo_id
            INNER JOIN om_product pr_in ON wi_in.om_product_id = pr_in.om_product_id
            WHERE wo_in.created_date BETWEEN %(start_date)s AND %(end_date)s
              AND (%(m_org_ids)s IS NULL OR wo_in.m_org_id = ANY(%(m_org_ids)s))
            GROUP BY pr_in.om_product_id
            ORDER BY SUM(wi_in.qty) DESC
            LIMIT 10
        )
        SELECT COUNT(DISTINCT wi.om_product_id) AS tot_items,
               COALESCE(SUM(wi.qty), 0)::float AS tot_qty,
               COUNT(DISTINCT wi.om_wo_id) AS tot_wo
        FROM om_wo_item wi
        JOIN om_wo w ON wi.om_wo_id = w.om_wo_id
        INNER JOIN top ON top.pid = wi.om_product_id
        WHERE w.created_date BETWEEN %(start_date)s AND %(end_date)s
          AND (%(m_org_ids)s IS NULL OR w.m_org_id = ANY(%(m_org_ids)s))
    """,
    "technician_performance": """
        SELECT COUNT(*) AS tot_teknisi,
               SUM(cnt) AS tot_wo,
               MAX(cnt) AS top_cnt,
               ROUND(AVG(cnt), 1) AS avg_cnt
        FROM (
            SELECT u.name, COUNT(DISTINCT w.om_wo_id) AS cnt
            FROM om_wo w
            INNER JOIN om_wo_appr appr ON w.om_wo_id = appr.om_wo_id
            INNER JOIN om_wo_appr_history apprh ON appr.om_wo_appr_id = apprh.om_wo_appr_id
            INNER JOIN m_user u ON apprh.last_approved = u.m_user_id
            WHERE apprh.last_approval IN (3, 4)
              AND w.created_date BETWEEN %(start_date)s AND %(end_date)s
              AND (%(m_org_ids)s IS NULL OR w.m_org_id = ANY(%(m_org_ids)s))
            GROUP BY u.name
            ORDER BY cnt DESC
            LIMIT 10
        ) t
    """,
    "asset_wo_summary": """
        SELECT COUNT(*) FILTER (WHERE type ILIKE 'SCH') AS sch,
               COUNT(*) FILTER (WHERE type ILIKE 'REQ') AS req,
               COUNT(*) FILTER (WHERE type ILIKE 'REQ' AND classification = 7) AS mec,
               COUNT(*) FILTER (WHERE type ILIKE 'REQ' AND classification = 8) AS ine,
               COUNT(*) FILTER (WHERE type ILIKE 'REQ' AND classification = 9) AS sip,
               COUNT(*) FILTER (WHERE type ILIKE 'REQ' AND classification = 10) AS gen
        FROM om_wo
        WHERE created_date BETWEEN %(start_date)s AND %(end_date)s
          AND (%(m_org_ids)s IS NULL OR m_org_id = ANY(%(m_org_ids)s))
    """,
    "wo_request": """
        SELECT COUNT(*) AS total,
               COUNT(*) FILTER (WHERE doc_status IN ('CO','RE','IP','DR')) AS open,
               COUNT(*) FILTER (WHERE doc_status = 'CL') AS closed,
               COUNT(*) FILTER (WHERE doc_status = 'RE') AS rejected
        FROM om_wo
        WHERE value ILIKE '%%REQ%%'
          AND created_date BETWEEN %(start_date)s AND %(end_date)s
          AND (%(m_org_ids)s IS NULL OR m_org_id = ANY(%(m_org_ids)s))
    """,
    "wo_durasi_proses": """
        WITH latest_appr AS (
            SELECT DISTINCT ON (appr.om_wo_id) appr.om_wo_id, appr.om_wo_appr_id
            FROM om_wo_appr appr
            ORDER BY appr.om_wo_id, appr.created_date DESC, appr.om_wo_appr_id DESC
        ),
        hist AS (
            SELECT la.om_wo_id,
                   MIN(h.created_date) AS submit_ts,
                   MIN(h.created_date) FILTER (WHERE h.last_status = 'CO') AS co_ts,
                   MIN(h.created_date) FILTER (WHERE h.last_status = 'CL') AS cl_ts
            FROM latest_appr la
            INNER JOIN om_wo_appr_history h ON h.om_wo_appr_id = la.om_wo_appr_id
            GROUP BY la.om_wo_id
        ),
        x AS (
            SELECT w.om_wo_id, w.created_date, w.closed_date, h.submit_ts, h.co_ts, h.cl_ts
            FROM om_wo w
            LEFT JOIN hist h USING (om_wo_id)
            WHERE w.doc_status = 'CL'
              AND w.created_date BETWEEN %(start_date)s AND %(end_date)s
              AND (%(m_org_ids)s IS NULL OR w.m_org_id = ANY(%(m_org_ids)s))
        )
        SELECT COUNT(*) AS total,
               ROUND(AVG(EXTRACT(EPOCH FROM (closed_date - created_date)) / 86400.0)::numeric, 1) AS avg_total_hari,
               ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP
                     (ORDER BY EXTRACT(EPOCH FROM (closed_date - created_date)) / 86400.0)::numeric, 1) AS med_total_hari,
               ROUND(AVG(EXTRACT(EPOCH FROM (co_ts - submit_ts)) / 86400.0)::numeric, 1) AS avg_approval_hari,
               ROUND(AVG(EXTRACT(EPOCH FROM (cl_ts - co_ts)) / 86400.0)::numeric, 1) AS avg_exec_hari,
               ROUND(PERCENTILE_CONT(0.9) WITHIN GROUP
                     (ORDER BY EXTRACT(EPOCH FROM (closed_date - created_date)) / 86400.0)::numeric, 1) AS p90_total_hari,
               ROUND(COUNT(*) FILTER (
                         WHERE EXTRACT(EPOCH FROM (closed_date - created_date)) / 86400.0 <= 7
                     ) * 100.0 / COUNT(*), 1) AS pct_dalam_7hari
        FROM x
    """,
}

ASSET_WO_SQL = """
    SELECT DISTINCT w.om_wo_id AS wo_id, w.value AS no_wo, w.description, w.doc_status AS status,
           w.created_date AS tanggal,
           COALESCE(cl.condition || ' - ' || cl.label, NULL) AS klasifikasi
    FROM om_wo w
    LEFT JOIN om_product pr ON w.asset_id = pr.om_product_id
    LEFT JOIN m_global_param cl ON cl.parent_condition = 'CLASSIFICATION_WO' AND cl.active = 'Y'
         AND cl.m_global_param_id = w.classification
    WHERE w.type ILIKE %(tipe)s
      AND COALESCE(pr.name, 'Tanpa Aset') = %(name)s
      AND w.created_date BETWEEN %(start_date)s AND %(end_date)s
      AND (%(m_org_ids)s IS NULL OR w.m_org_id = ANY(%(m_org_ids)s))
    ORDER BY w.created_date DESC
"""

WO_LIST_SQL = """
    SELECT DISTINCT w.om_wo_id AS wo_id, w.value AS no_wo, w.description, w.doc_status AS status,
           w.created_date AS tanggal, w.type AS tipe,
           COALESCE(cl.condition || ' - ' || cl.label, NULL) AS klasifikasi,
           COALESCE(pr.name, 'Tanpa Aset') AS aset, o.name AS site
    FROM om_wo w
    LEFT JOIN om_product pr ON w.asset_id = pr.om_product_id
    LEFT JOIN m_org o ON w.m_org_id = o.m_org_id
    LEFT JOIN m_global_param cl ON cl.parent_condition = 'CLASSIFICATION_WO' AND cl.active = 'Y'
         AND cl.m_global_param_id = w.classification
    WHERE w.created_date BETWEEN %(start_date)s AND %(end_date)s
      AND (%(m_org_ids)s IS NULL OR w.m_org_id = ANY(%(m_org_ids)s))
      AND (%(tipe)s IS NULL OR w.type ILIKE %(tipe)s)
      AND (%(aset)s IS NULL OR COALESCE(pr.name, 'Tanpa Aset') = %(aset)s)
      AND (%(site)s IS NULL OR o.name = %(site)s)
      AND (%(bulan)s IS NULL OR to_char(w.created_date, 'YYYY-MM') = %(bulan)s)
      AND (%(teknisi)s IS NULL OR w.om_wo_id IN (
          SELECT DISTINCT a.om_wo_id
          FROM om_wo_appr a
          JOIN om_wo_appr_history h ON h.om_wo_appr_id = a.om_wo_appr_id
          JOIN m_user u ON h.last_approved = u.m_user_id
          WHERE u.name = %(teknisi)s AND h.last_approval IN (3, 4)))
      AND (%(status)s IS NULL OR
           (CASE %(status)s
             WHEN 'open' THEN w.doc_status IN ('CO','RE','IP','DR')
             WHEN 'backlog' THEN w.doc_status IN ('CO','RE','IP','DR')
             WHEN 'closed' THEN w.doc_status = 'CL'
             ELSE TRUE END))
    ORDER BY w.created_date DESC
"""

SPAREPART_WO_SQL = """
    SELECT DISTINCT w.om_wo_id AS wo_id, w.value AS no_wo, w.description, w.doc_status AS status,
           w.created_date AS tanggal
    FROM om_wo_item wi
    JOIN om_wo w ON wi.om_wo_id = w.om_wo_id
    INNER JOIN om_product pr ON wi.om_product_id = pr.om_product_id
    WHERE pr.name = %(name)s
      AND w.created_date BETWEEN %(start_date)s AND %(end_date)s
      AND (%(m_org_ids)s IS NULL OR w.m_org_id = ANY(%(m_org_ids)s))
    ORDER BY w.created_date DESC
"""

KPI_SITE_RAW_SQL = """
    SELECT o.m_org_id AS site_id, o.name AS site_name,
           w.type AS tipe, w.doc_status AS status, w.om_wo_id AS wo_id, w.budget
    FROM om_wo w
    INNER JOIN m_org o ON w.m_org_id = o.m_org_id
    WHERE w.created_date BETWEEN %(start_date)s AND %(end_date)s
      AND (%(m_org_ids)s IS NULL OR w.m_org_id = ANY(%(m_org_ids)s))
"""

TREN_BULANAN_RAW_SQL = """
    SELECT w.created_date AS created, w.type AS tipe, w.budget
    FROM om_wo w
    WHERE w.created_date BETWEEN %(start_date)s AND %(end_date)s
      AND (%(m_org_ids)s IS NULL OR w.m_org_id = ANY(%(m_org_ids)s))
"""

PARETO_RAW_SQL = """
    SELECT pr.name AS sparepart, wi.qty
    FROM om_wo_item wi
    JOIN om_wo w ON wi.om_wo_id = w.om_wo_id
    INNER JOIN om_product pr ON wi.om_product_id = pr.om_product_id
    WHERE w.created_date BETWEEN %(start_date)s AND %(end_date)s
      AND (%(m_org_ids)s IS NULL OR w.m_org_id = ANY(%(m_org_ids)s))
"""

MTBF_MTTR_RAW_SQL = """
    SELECT pr.name AS aset, w.doc_status AS status,
           w.created_date AS created, w.closed_date AS closed
    FROM om_wo w
    INNER JOIN om_product pr ON w.asset_id = pr.om_product_id
    WHERE w.type ILIKE 'SCH'
      AND w.asset_id IS NOT NULL
      AND w.created_date BETWEEN %(start_date)s AND %(end_date)s
      AND (%(m_org_ids)s IS NULL OR w.m_org_id = ANY(%(m_org_ids)s))
"""

PROFIL_TEKNISI_BASE_SQL = """
    SELECT w.om_wo_id AS wo_id, w.value AS no_wo, w.doc_status AS status,
           w.created_date AS created, hist.start_ts, hist.cl_ts
    FROM om_wo w
    LEFT JOIN (
        SELECT a.om_wo_id,
               MIN(h.created_date) AS start_ts,
               MAX(h.created_date) FILTER (WHERE h.last_status = 'CL') AS cl_ts
        FROM om_wo_appr a
        JOIN om_wo_appr_history h ON a.om_wo_appr_id = h.om_wo_appr_id
        GROUP BY a.om_wo_id
    ) hist ON hist.om_wo_id = w.om_wo_id
    WHERE w.created_date BETWEEN %(start_date)s AND %(end_date)s
      AND (%(m_org_ids)s IS NULL OR w.m_org_id = ANY(%(m_org_ids)s))
"""

PROFIL_TEKNISI_EVENT_SQL = """
    SELECT w.om_wo_id AS wo_id, h.created_date AS ts, u.name AS teknisi
    FROM om_wo w
    JOIN om_wo_appr appr ON w.om_wo_id = appr.om_wo_id
    JOIN om_wo_appr_history h ON h.om_wo_appr_id = appr.om_wo_appr_id
    JOIN m_user u ON h.last_approved = u.m_user_id
    WHERE h.last_approval IN (3, 4)
      AND w.created_date BETWEEN %(start_date)s AND %(end_date)s
      AND (%(m_org_ids)s IS NULL OR w.m_org_id = ANY(%(m_org_ids)s))
"""

TECHNISI_BACKLOG_SQL = """
    SELECT last.wo_id, u.name AS teknisi, last.status
    FROM (
        SELECT DISTINCT ON (a.om_wo_id) a.om_wo_id AS wo_id,
               h.last_approved AS uid, w.doc_status AS status,
               h.created_date AS cd, h.om_wo_appr_history_id AS hid
        FROM om_wo_appr a
        JOIN om_wo_appr_history h ON a.om_wo_appr_id = h.om_wo_appr_id
        JOIN om_wo w ON w.om_wo_id = a.om_wo_id
        ORDER BY a.om_wo_id, h.created_date DESC, h.om_wo_appr_history_id DESC
    ) last
    JOIN m_user u ON last.uid = u.m_user_id
"""

DATA_QUALITY_RAW_SQL = """
    SELECT w.om_wo_id AS wo_id, w.value AS no_wo, w.created_date AS created,
           w.closed_date AS closed, w.updated_date AS updated,
           w.asset_id, w.classification, w.doc_status AS status, w.type AS tipe
    FROM om_wo w
    WHERE w.created_date BETWEEN %(start_date)s AND %(end_date)s
      AND (%(m_org_ids)s IS NULL OR w.m_org_id = ANY(%(m_org_ids)s))
"""

COMPARE_RAW_SQL = """
    SELECT DISTINCT w.om_wo_id AS wo_id, w.type AS tipe, w.doc_status AS status,
           w.created_date AS tanggal, w.budget, o.name AS site,
           COALESCE(pr.name, 'Tanpa Aset') AS aset,
           COALESCE(tek.name, 'Tanpa Teknisi') AS teknisi
    FROM om_wo w
    LEFT JOIN om_product pr ON w.asset_id = pr.om_product_id
    LEFT JOIN m_org o ON w.m_org_id = o.m_org_id
    LEFT JOIN LATERAL (
        SELECT u.name AS name
        FROM om_wo_appr a
        INNER JOIN om_wo_appr_history h ON a.om_wo_appr_id = h.om_wo_appr_id
        INNER JOIN m_user u ON h.last_approved = u.m_user_id
        WHERE a.om_wo_id = w.om_wo_id AND h.last_approval IN (3, 4)
        ORDER BY h.created_date DESC, h.om_wo_appr_history_id DESC
        LIMIT 1
    ) tek ON TRUE
    WHERE w.created_date BETWEEN %(start_date)s AND %(end_date)s
      AND (%(m_org_ids)s IS NULL OR w.m_org_id = ANY(%(m_org_ids)s))
      AND (%(tipe)s IS NULL OR w.type ILIKE %(tipe)s)
      AND (%(aset)s IS NULL OR COALESCE(pr.name, 'Tanpa Aset') = %(aset)s)
      AND (%(site)s IS NULL OR o.name = %(site)s)
      AND (%(teknisi)s IS NULL OR tek.name = %(teknisi)s)
    ORDER BY w.created_date DESC
"""

COMPARE_REFS_SQL = {
    "aset": """
        SELECT DISTINCT pr.name AS name
        FROM om_product pr
        WHERE pr.name IS NOT NULL AND pr.name <> ''
        ORDER BY pr.name
        LIMIT 2000
    """,
    "teknisi": """
        SELECT DISTINCT u.name AS name
        FROM om_wo_appr a
        INNER JOIN om_wo_appr_history h ON a.om_wo_appr_id = h.om_wo_appr_id
        INNER JOIN m_user u ON h.last_approved = u.m_user_id
        WHERE h.last_approval IN (3, 4) AND u.name IS NOT NULL AND u.name <> ''
        ORDER BY u.name
        LIMIT 2000
    """,
}