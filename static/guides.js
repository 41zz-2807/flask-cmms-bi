/**
 * Panduan Membaca Dashboard — konten ditulis sebagai HTML sehingga mudah
 * diedit tanpa mengubah logika aplikasi. Kunci = id kategori halaman.
 */
window.BI_GUIDES = (function () {

  var GLOSSARY =
    '<div class="g-title">Istilah Umum yang Dipakai di Halaman Ini</div>' +
    '<table class="g-cols">' +
    '<tr><th>WO (Work Order)</th><td>Perintah/tugas kerja pemeliharaan yang tercatat di sistem CMMS. Satu WO = satu pekerjaan.</td></tr>' +
    '<tr><th>SCH</th><td>WO <b>terjadwal</b> (rutin / preventive maintenance) — jadwal perawatan berkala.</td></tr>' +
    '<tr><th>REQ</th><td>WO <b>permintaan</b> / tidak terjadwal (corrective / insidental) — karena ada kerusakan atau permintaan lain.</td></tr>' +
    '<tr><th>CL (Closed)</th><td>WO sudah <b>selesai</b> dan ditutup.</td></tr>' +
    '<tr><th>CO</th><td>WO baru <b>dibuat/dibuka</b> (Created) — belum diproses.</td></tr>' +
    '<tr><th>RE</th><td>WO <b>diajukan</b> (Request) — menunggu persetujuan/proses berikutnya.</td></tr>' +
    '<tr><th>IP</th><td>WO <b>sedang dikerjakan</b> (In Progress).</td></tr>' +
    '<tr><th>DR</th><td>WO masih <b>draft/konsep</b> — belum lengkap.</td></tr>' +
    '<tr><th>Open</th><td>Gabungan status yang <b>belum selesai</b>: CO + RE + IP + DR.</td></tr>' +
    '<tr><th>Site</th><td>Lokasi/area kerja (HO, BCP - SENG, GHSF, SSDS &amp; SSGP, dll.).</td></tr>' +
    '<tr><th>Periode</th><td>Rentang tanggal yang difilter (kolom <b>Dari</b> s/d <b>to</b>). Semua angka pada halaman mengikuti filter ini.</td></tr>' +
    '</table>' +
    '<p class="g-note">Penamaan kode status mengikuti sistem CMMS; keterangan dalam tanda kurung adalah pengertian umumnya agar mudah dipahami.</p>';

  window.BI_GLOSSARY = GLOSSARY;

  return {
    home: {
      intro:
        '<p>Halaman ini adalah <b>pintu masuk semua dashboard</b>. Dashboard dikelompokkan menurut tema, dan setiap kartu mewakili satu laporan/analisis. Klik kartu untuk membuka laporan detailnya.</p>' +
        '<p>Cara cepat membaca: <b>angka di kartu lokasi (Semua Site)</b> memberi gambaran umum dulu (total WO, status selesai, biaya), lalu klik kartu tema untuk melihat rinciannya.</p>',
      chart: null,
      table: '<p><b>Kelompok dashboard:</b></p>' +
        '<ul>' +
        '<li><b>Ringkasan &amp; KPI</b> — KPI per Site, tren bulanan, dan WO termahal. Untuk lihat kesehatan keseluruhan.</li>' +
        '<li><b>Pemeliharaan &amp; Keandalan</b> — rekap WO per aset, kepatuhan jadwal PM, MTBF/MTTR, dan aset paling sering bermasalah.</li>' +
        '<li><b>Sparepart &amp; Material</b> — analisis prioritas sparepart (ABC) dan sparepart fast-moving.</li>' +
        '<li><b>Sumber Daya &amp; Teknisi</b> — beban kerja dan profil teknisi.</li>' +
        '<li><b>Kesehatan Data</b> — laporan kualitas data (menemukan WO yang catatannya salah/kurang).</li>' +
        '</ul>' +
        '<p><b>Filter:</b> pilih rentang tanggal <b>Dari s/d</b>, lalu centang site tertentu bila ingin fokus ke lokasi tertentu. Tanpa centang = "Semua Site".</p>' +
        '<p>Tombol <b>Perbandingan Dinamis</b> di pojok kanan atas membuka alat membandingkan kinerja antar periode/site.</p>',
      columns: [],
    },
    kpi_site: {
      intro:
        '<p>Merangkum kinerja operasional tiap <b>site</b> (lokasi kerja) pada periode terpilih — seberapa banyak pekerjaan, seberapa banyak yang sudah selesai, dan berapa biayanya. Cocok untuk pemantauan harian/bulanan tiap area.</p>',
      chart:
        '<p>Grafik <b>batang vertikal</b>: satu batang = satu site, tinggi batang = jumlah WO di site itu. Semakin tinggi, semakin banyak pekerjaan pemeliharaan yang terjadi di area tersebut (bisa berarti area sibuk/bermasalah).</p>',
      table:
        '<p>Baris <b>per site</b>, dan baris terakhir <b>"Semua Site"</b> adalah rekap gabungan seluruh lokasi. Perhatikan kolom <b>% Closed</b> dan <b>% PM</b>: angka rendah menandakan pekerjaan yang belum tuntas.</p>',
      columns: [
        ["site", "Nama lokasi/area kerja. Baris \"Semua Site\" = gabungan seluruh area."],
        ["total_wo", "Jumlah seluruh WO di periode & site ini."],
        ["sch", "WO terjadwal/rutin (preventive maintenance)."],
        ["req", "WO permintaan/tidak terjadwal (perbaikan)."],
        ["open", "WO yang masih berstatus terbuka (belum selesai)."],
        ["pct_closed", "Persentase WO selesai (CL). 100% = semua tuntas."],
        ["pct_pm", "Kepatuhan menjalankan jadwal PM: % WO rutin yang berhasil ditutup. Target umum &ge; 80%."],
        ["budget", "Total biaya (budget) seluruh WO di periode ini."],
        ["budget_closed", "Total biaya dari WO yang sudah selesai (CL)."],
        ["avg_budget", "Rata-rata biaya per WO."],
      ],
    },
    tren_bulanan: {
      intro:
        '<p>Menampilkan <b>pola dan arah</b> jumlah pekerjaan dari bulan ke bulan, lengkap dengan indikator musiman. Berguna untuk merencanakan kapasitas teknis (apakah beban sedang naik atau menurun).</p>',
      chart:
        '<p>Grafik <b>garis/batang per bulan</b>: biasanya ada tiga garis — <b>total</b>, <b>SCH</b>, dan <b>REQ</b>.</p>' +
        '<p>Cara membaca: lihat arah garis total. <b>Menaik</b> berarti beban kerja bertambah, <b>menurun</b> berarti berkurang, <b>datar</b> berarti stabil. Garis <b>MA-3 (rata-rata bergerak 3 bulan)</b> yang lebih halus membantu melihat tren yang sebenarnya tanpa terpengaruh lonjakan satu bulan.</p>',
      table: null,
      columns: [
        ["bulan", "Bulan pada periode (format YYYY-MM)."],
        ["total", "Jumlah seluruh WO di bulan itu."],
        ["sch", "Jumlah WO rutin terjadwal (SCH)."],
        ["req", "Jumlah WO permintaan (REQ)."],
        ["biaya", "Total biaya (budget) WO bulan itu."],
        ["mom_total", "Perubahan dibanding <b>bulan sebelumnya</b> (%). + berarti naik, − berarti turun."],
        ["yoy_total", "Perubahan dibanding <b>bulan yang sama tahun lalu</b> (%)."],
        ["ma3_total", "Rata-rata bergerak 3 bulan (meratakan fluktuasi antar bulan)."],
        ["seasonal", "Indeks musiman: &gt; 1 = bulan ini biasanya lebih ramai dari rata-rata; &lt; 1 = lebih sepi."],
      ],
    },
    biaya_wo: {
      intro:
        '<p>Menampilkan <b>WO dengan biaya tertinggi</b> pada periode terpilih. Tujuannya melihat ke mana anggaran paling banyak terserap dan mengevaluasi pekerjaan yang mahal.</p>',
      chart:
        '<p>Grafik <b>batang horizontal</b>: satu batang = satu WO, panjang batang = besarnya biaya (budget). WO paling atas adalah yang paling mahal.</p>',
      table:
        '<p>Daftar WO dari biaya tertinggi ke terendah. Klik <b>No. WO</b> untuk membuka dokumen WO bila tersedia.</p>',
      columns: [
        ["no_wo", "Nomor WO."],
        ["description", "Uraian singkat pekerjaan yang dilakukan."],
        ["status", "Status WO (CL = selesai, dst.)."],
        ["tanggal", "Tanggal WO dibuat."],
        ["budget", "Biaya pekerjaan tersebut (Rp)."],
      ],
    },
    asset_wo_summary: {
      intro:
        '<p>Rekapitulasi WO <b>per aset</b>: berapa banyak aset meminta WO rutin (SCH) dan WO permintaan (REQ). Berguna untuk melihat aset mana yang paling banyak menuntut perhatian.</p>',
      chart: '<p>Halaman ini <b>tidak menampilkan grafik</b> — langsung berupa tabel rekap dan kartu ringkasan.</p>',
      table:
        '<p>Setiap baris = satu aset. Klik angka pada kolom <b>WO SCH</b>/<b>WO REQ</b> untuk membuka daftar WO-nya. Baris <b>"Tanpa Aset"</b> menandakan WO yang tidak terhubung ke aset (sebaiknya diperbaiki datanya).</p>' +
        '<p>Kartu ringkasan menunjukkan pembagian jenis pekerjaan REQ: <b>MEC</b> (mekanikal), <b>INE</b> (instrument &amp; electrical), <b>SIP</b> (sipil), <b>GEN</b> (general).</p>',
      columns: [
        ["aset", "Nama aset. Baris \"Tanpa Aset\" = WO tanpa keterkaitan aset."],
        ["sch_total", "Jumlah WO rutin terjadwal untuk aset ini (tombol → daftar WO SCH)."],
        ["req_total", "Jumlah WO permintaan untuk aset ini (tombol → daftar WO REQ)."],
        ["status", "Status WO paling terakhir pada aset ini."],
        ["tanggal", "Tanggal WO paling terakhir pada aset ini."],
      ],
    },
    pm_compliance: {
      intro:
        '<p>Mengukur <b>kepatuhan pemeliharaan rutin terjadwal</b> (preventive maintenance/SCH). Target umum kepatuhan adalah <b>&ge; 80%</b> — artinya minimal 8 dari 10 WO jadwal berhasil diselesaikan.</p>',
      chart:
        '<p>Grafik <b>lingkaran (pie)</b>: membagi seluruh WO jadwal (SCH) berdasarkan statusnya. Potongan <b>CL</b> (hijau, selesai) adalah porsi yang telat tertunda; makin besar potongan "belum selesai", makin rendah kepatuhan.</p>',
      table:
        '<p>Daftar semua WO rutin (SCH) pada periode. Gunakan kolom <b>Status</b> untuk melihat mana yang belum CL.</p>',
      columns: [
        ["no_wo", "Nomor WO (klik untuk membuka dokumen bila ada)."],
        ["description", "Uraian pekerjaan rutin."],
        ["status", "Status WO (CL = selesai; lainnya = belum selesai)."],
        ["tanggal", "Tanggal WO dibuat."],
        ["tipe", "Jenis WO — pada halaman ini selalu SCH."],
      ],
    },
    mtbf_mttr: {
      intro:
        '<p>Menilai <b>keandalan aset</b>: (1) seberapa jarang aset rusak, dan (2) seberapa cepat perbaikan dilakukan. Dua metrik utama:</p>' +
        '<ul>' +
        '<li><b>MTBF</b> (Mean Time Between Failures) = rata-rata <b>jarak antar kerusakan</b>. <b>Makin besar makin baik</b> — aset jarang rusak.</li>' +
        '<li><b>MTTR</b> (Mean Time To Repair) = rata-rata <b>waktu perbaikan</b> sejak WO dibuat sampai ditutup. <b>Makin kecil makin baik</b> — perbaikan cepat.</li>' +
        '</ul>',
      chart:
        '<p>Grafik dua batang per aset: <b>oranye = MTTR</b> (waktu perbaikan), <b>biru = MTBF</b> (jarak antar kerusakan), satuan <b>hari</b>.</p>' +
        '<p>Beri perhatian pada aset dengan <b>MTBF sangat kecil</b> (sering rusak) dan/atau <b>MTTR besar</b> (lambat diperbaiki) — keduanya mengindikasikan butuh analisis akar masalah (RCA).</p>',
      table: null,
      columns: [
        ["aset", "Nama aset."],
        ["wo_total", "Jumlah kejadian (WO SCH) pada aset ini dalam periode — seberapa sering aset bermasalah."],
        ["mttr", "MTTR dalam hari — rata-rata waktu perbaikan. Kecil = cepat selesai diperbaiki."],
        ["mtbf", "MTBF dalam hari — rata-rata jarak antar kerusakan. Besar = jarang rusak."],
        ["last_date", "Tanggal WO (kejadian) terakhir pada aset ini."],
        ["status_terakhir", "Status WO terakhir pada aset ini."],
      ],
    },
    asset_wo_frequency: {
      intro:
        '<p>Menampilkan <b>10 aset yang paling sering membuat WO</b>. Frekuensi tinggi bisa berarti aset tersebut sudah tua/bermasalah, butuh renovasi, atau butuh jadwal PM yang lebih baik.</p>',
      chart:
        '<p>Grafik <b>batang horizontal</b>: satu batang = satu aset, panjang = jumlah WO. Aset di bagian atas adalah yang paling sering bermasalah.</p>',
      table:
        '<p>Daftar WO dari 10 aset teratas tersebut (terbaru di atas). Klik <b>No. WO</b> untuk membuka dokumen bila tersedia.</p>',
      columns: [
        ["no_wo", "Nomor WO."],
        ["description", "Uraian pekerjaan."],
        ["status", "Status WO."],
        ["tanggal", "Tanggal WO dibuat."],
        ["aset", "Nama aset tempat WO terjadi."],
      ],
    },
    pareto_sparepart: {
      intro:
        '<p>Analisis <b>Pareto/ABC untuk sparepart</b> (aturan 80/20): sebagian kecil jenis sparepart justru menyerap sebagian besar pemakaian. Tujuannya memprioritaskan pengadaan &amp; stok ke sparepart yang kritis.</p>' +
        '<p>Pembagian kelas berdasarkan <b>kumulatif pemakaian</b>:</p>' +
        '<ul>' +
        '<li><b>Kelas A</b> — sampai dengan 80% kumulatif. Sedikit jenis tapi paling banyak dipakai / bernilai tinggi. <b>Prioritas utama</b>: dijaga stoknya, dievaluasi pengadaannya.</li>' +
        '<li><b>Kelas B</b> — kumulatif 80%–95%. Menengah.</li>' +
        '<li><b>Kelas C</b> — di atas 95%. Banyak jenis tetapi pemakaiannya kecil.</li>' +
        '</ul>',
      chart:
        '<p>Grafik <b>pareto</b>: batang = jumlah pemakaian per sparepart (diurut menurun), garis <b>kumulatif %</b> menunjukkan akumulasi pemakaian. Lihat titik garis kumulatif menembus <b>80%</b> dan <b>95%</b> — itulah batas pemisah kelas A/B/C.</p>',
      table: null,
      columns: [
        ["sparepart", "Nama sparepart."],
        ["qty", "Jumlah satuan yang terpakai pada periode."],
        ["share", "Kontribusi sparepart ini terhadap total pemakaian (%)."],
        ["cum", "Kontribusi kumulatif sampai baris ini (+ baris sebelumnya)."],
        ["klas", "Kelas prioritas: <span class=\"g-tag\">A</span> kritis (≤80%), <span class=\"g-tag\">B</span> menengah, <span class=\"g-tag\">C</span> rendah."],
      ],
    },
    sparepart_fast_moving: {
      intro:
        '<p>Menampilkan <b>10 sparepart yang paling cepat habis</b> (fast-moving). Berguna untuk memastikan min-max stock dan kontrak pengadaan mengikuti laju pemakaian.</p>',
      chart:
        '<p>Grafik <b>batang horizontal</b>: panjang batang = jumlah satuan terpakai. Bagian atas = sparepart paling boros.</p>',
      table:
        '<p>Kolom <b>Jumlah WO</b> berupa tombol — klik untuk membuka daftar WO yang memakai sparepart tersebut.</p>',
      columns: [
        ["sparepart", "Nama sparepart."],
        ["jmlwo", "Jumlah WO yang memakai sparepart ini (tombol → daftar WO)."],
        ["tanggal", "Tanggal pemakaian terakhir."],
        ["status", "Status WO pemakaian terakhir."],
      ],
    },
    profil_teknisi: {
      intro:
        '<p>Profil <b>beban kerja dan kecepatan kerja teknisi</b>: siapa yang paling banyak menangani WO, seberapa cepat pekerjaannya tuntas, dan berapa pekerjaan yang masih menggantung (backlog).</p>',
      chart:
        '<p>Grafik <b>batang bertumpuk per bulan</b>: setiap warna = satu teknisi, tinggi bagian warna = jumlah WO yang ditangani teknisi itu pada bulan tsb. Cara membaca: lihat <b>distribusi warna</b> — kalau bebannya miring ke satu warna terus-menerus, distribusi pekerjaan tidak merata.</p>',
      table: null,
      columns: [
        ["teknisi", "Nama teknisi. \"Tanpa Teknisi\" = WO yang belum ada penanggung jawabnya."],
        ["wo_total", "Total WO yang diproses teknisi ini."],
        ["wo_cl", "Jumlah WO yang berhasil diselesaikan (CL)."],
        ["med_hari", "Median lama penyelesaian dalam hari — setengah pekerjaan selesai lebih cepat, setengahnya lagi lebih lambat. Kecil = cepat."],
        ["p95_hari", "Nilai P95: 95% pekerjaan selesai dalam angka ini. Menunjukkan kecepatan pada kasus-kasus yang lambat."],
        ["backlog", "Jumlah WO terbuka yang sedang ditangani. Besar = banyak pekerjaan menumpuk."],
      ],
    },
    technician_performance: {
      intro:
        '<p>Perbandingan <b>beban kerja antar teknisi</b> (jumlah WO yang dikerjakan/disetujui) pada periode terpilih, beserta lama pengerjaan.</p>',
      chart:
        '<p>Grafik <b>batang horizontal</b>: satu batang = satu teknisi, panjang = jumlah WO. Teknisi teratas menangani paling banyak — perhatikan apakah bebannya tidak seimbang.</p>',
      table:
        '<p>Daftar WO yang pernah ditangani teknisi teratas, dengan kolom <b>Durasi Waktu</b> (lama pengerjaan dalam hari/jam/menit berdasarkan catatan sistem).</p>',
      columns: [
        ["no_wo", "Nomor WO."],
        ["description", "Uraian pekerjaan."],
        ["status", "Status WO."],
        ["tanggal", "Tanggal WO dibuat."],
        ["teknisi", "Nama teknisi penanggung jawab."],
        ["durasi", "Lama pengerjaan (dari catatan persetujuan sistem)."],
      ],
    },
    data_quality: {
      intro:
        '<p>Laporan <b>kualitas data</b>: mendeteksi WO yang catatannya salah atau tidak lengkap di sistem CMMS. Data yang bersih penting agar semua angka dashboard lain bisa dipercaya.</p>',
      chart:
        '<p>Grafik <b>batang</b>: satu batang = satu jenis masalah, tinggi = jumlah WO terdampak. Fokus pada kategori dengan batang tertinggi terlebih dahulu.</p>',
      table: '<p>Daftar WO bermasalah beserta keterangan spesifiknya (kolom <b>Detail</b>).</p>',
      columns: [
        ["kategori", "Jenis masalah:"],
        ["no_wo", "Nomor WO yang bermasalah."],
        ["tanggal", "Tanggal WO (jika ada)."],
        ["status", "Status WO."],
        ["detail", "Penjelasan spesifik masalah pada WO tersebut."],
      ].concat([
        ["— Tanpa Aset", "WO tidak terkait dengan aset apa pun."],
        ["— Tanpa Klasifikasi", "WO REQ tanpa klasifikasi jenis pekerjaan."],
        ["— Tanggal Tidak Masuk Akal", "Tanggal selesai lebih awal daripada tanggal dibuat."],
        ["— Konsistensi Status", "Status CL (selesai) tetapi tanggal selesainya kosong."],
        ["— Tanggal Futuristik", "Tanggal WO tercatat di masa depan."],
        ["— Duplikat", "Nomor WO yang sama muncul lebih dari sekali."],
      ]),
    },
    compare: {
      intro:
        '<p>Alat untuk <b>membandingkan kinerja</b> antar periode/lokasi/aset/teknisi. Anda membuat beberapa <b>grup</b> (masing-masing = kombinasi periode + saringan), lalu dashboard menghitung metrik tiap grup dan <b>selisihnya terhadap grup acuan</b>.</p>' +
        '<p>Langkah:</p>' +
        '<ol>' +
        '<li><b>Definisikan Grup Perbandingan</b> — untuk tiap grup pilih nama, rentang tanggal, dan (opsional) saringan site/aset/teknisi.</li>' +
        '<li><b>Pilih Metrik</b> yang dibandingkan (Total WO, % Closed, biaya, dsb.).</li>' +
        '<li><b>Acuan Perbandingan (Delta)</b> — pilih grup pembanding; semua grup akan dihitung selisihnya terhadap grup ini.</li>' +
        '<li><b>Metrik untuk Grafik</b> — pilih metrik yang digambar pada grafik.</li>' +
        '<li>Klik <b>Hitung Perbandingan</b>.</li>' +
        '</ol>',
      chart:
        '<p>Grafik menampilkan nilai metrik terpilih untuk tiap grup (satu garis/batang per grup). Semakin ke atas = nilai semakin besar (untuk metrik seperti % Closed atau Total WO).</p>',
      table:
        '<p>Tabel hasil perbandingan: satu baris = satu metrik, satu kolom = satu grup, plus kolom <b>delta</b> (selisih terhadap grup acuan).</p>' +
        '<p>Warna delta: <b class="g-delta-up">hijau</b> = lebih tinggi/naik, <b class="g-delta-down">merah</b> = lebih rendah/turun, <b class="g-delta-zero">abu-abu</b> = tidak berubah. Untuk metrik biaya, naik belum tentu buruk — nilailah sesuai konteks.</p>' +
        '<p>Baris <b>Rata-rata</b> di bawah tabel adalah rekap nilai rata-rata seluruh grup.</p>',
      columns: [
        ["total_wo", "Jumlah seluruh WO dalam grup."],
        ["sch", "WO rutin terjadwal (SCH)."],
        ["req", "WO permintaan (REQ)."],
        ["open", "WO yang masih terbuka / belum selesai."],
        ["closed", "WO yang sudah selesai (CL)."],
        ["pct_closed", "Persentase WO selesai: closed / total (%)."],
        ["budget", "Total biaya seluruh WO (Rp)."],
        ["avg_budget", "Rata-rata biaya per WO (Rp)."],
        ["backlog", "Jumlah WO terbuka (sama dengan open)."],
      ],
      glossary: false,
    },
  };
})();

/** Render panduan ke dalam elemen. key = kunci kamus BI_GUIDES. */
window.renderGuide = function (el, key) {
  if (!el) return;
  var g = window.BI_GUIDES && window.BI_GUIDES[key];
  if (!g) {
    el.closest(".guide") && (el.closest(".guide").style.display = "none");
    return;
  }
  var html = "";
  if (g.intro) html += '<p class="g-lead">' + g.intro + "</p>";
  if (g.chart) html += '<h4>Cara Membaca Grafik</h4><div class="g-sec">' + g.chart + "</div>";
  if (g.table) html += '<h4>Cara Membaca Tabel</h4><div class="g-sec">' + g.table + "</div>";
  if (g.columns && g.columns.length) {
    html += '<h4>Penjelasan Kolom Tabel</h4><div class="g-sec"><table class="g-cols"><tbody>';
    g.columns.forEach(function (r) {
      html += "<tr><th>" + r[0] + "</th><td>" + r[1] + "</td></tr>";
    });
    html += "</tbody></table></div>";
  }
  if (g.glossary !== false) html += '<div class="g-sec g-gloss">' + window.BI_GLOSSARY + "</div>";
  el.innerHTML = html;
};