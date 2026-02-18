import com.comsol.model.*;
import com.comsol.model.util.*;
import java.io.*;
import java.nio.file.*;
import java.util.*;

public class run_sweeps {

  public static Map<String, String> defaultParams() {
    Map<String, String> p = new LinkedHashMap<String, String>();
    p.put("case_id", "default_case");
    p.put("geometry", "3d");
    p.put("mode", "578");
    p.put("useBioheat", "0");
    p.put("exportFigures", "0");
    p.put("D", "2.0e-4");
    p.put("depth", "4.0e-4");
    p.put("tp", "2.0e-4");
    p.put("f", "1000");
    p.put("Npulses", "10");
    p.put("w0", "5.0e-4");
    p.put("extra_cool", "0.2");
    p.put("A_578", "6.0e8");
    p.put("A_511", "5.0e8");
    p.put("mu_eff_578", "1200");
    p.put("mu_eff_511", "1700");
    p.put("p578", "0.7");
    p.put("p511", "0.3");
    p.put("wb", "0.005");
    p.put("cb", "3600");
    p.put("rho", "1100");
    p.put("Cp", "3400");
    p.put("k", "0.45");
    p.put("T0", "310.15");
    p.put("T_blood", "310.15");
    p.put("Lx", "4.0e-3");
    p.put("Ly", "4.0e-3");
    p.put("Lz", "3.0e-3");
    p.put("Rmax2D", "3.0e-3");
    p.put("Zmax2D", "3.0e-3");
    p.put("dtmax_factor", "0.1");
    return p;
  }

  public static List<Map<String, String>> readSweepCsv(String csvPath) throws IOException {
    List<Map<String, String>> rows = new ArrayList<Map<String, String>>();
    List<String> lines = Files.readAllLines(Paths.get(csvPath));
    if (lines.isEmpty()) return rows;

    String[] headers = lines.get(0).split(",");
    for (int i = 1; i < lines.size(); i++) {
      String line = lines.get(i).trim();
      if (line.isEmpty() || line.startsWith("#")) continue;
      String[] vals = line.split(",");
      Map<String, String> row = defaultParams();
      for (int c = 0; c < headers.length && c < vals.length; c++) {
        row.put(headers[c].trim(), vals[c].trim());
      }
      rows.add(row);
    }
    return rows;
  }

  public static Map<String, String> readBaselineJson(String jsonPath) {
    Map<String, String> map = defaultParams();
    try {
      String text = new String(Files.readAllBytes(Paths.get(jsonPath)));
      text = text.replace("{", "").replace("}", "").trim();
      String[] pairs = text.split(",");
      for (String pair : pairs) {
        String[] kv = pair.split(":", 2);
        if (kv.length != 2) continue;
        String key = kv[0].replace("\"", "").trim();
        String val = kv[1].replace("\"", "").trim();
        map.put(key, val);
      }
    } catch (Exception ignored) {}
    return map;
  }

  private static void applyModeFlag(Model model, String mode) {
    if ("578_511".equalsIgnoreCase(mode)) {
      model.param().set("modeflag", "2");
    } else {
      model.param().set("modeflag", "1");
    }
  }

  private static void runOneCase(Map<String, String> p, Map<String, String> baseline) throws Exception {
    String caseId = p.get("case_id");
    String geometry = p.get("geometry");

    Model model;
    if ("2d".equalsIgnoreCase(geometry)) {
      model = build_model_2d_axi.buildFromMap(p, caseId);
    } else {
      model = build_model_3d.buildFromMap(p, caseId);
    }

    applyModeFlag(model, p.get("mode"));

    model.sol("sol1").runAll();
    String mphPath = "results/models/" + caseId + ".mph";
    model.save(mphPath);

    postprocess.Metrics m = postprocess.evaluate(model);
    postprocess.appendMetricsCsv("results/metrics.csv", p, m);

    String baselineId = baseline.get("case_id");
    if ("1".equals(p.get("exportFigures")) || caseId.equals(baselineId)) {
      postprocess.exportFigures(model, caseId, geometry);
    }

    ModelUtil.remove("Model");
  }

  public static void main(String[] args) throws Exception {
    Files.createDirectories(Paths.get("results"));
    Files.createDirectories(Paths.get("results/models"));
    Files.createDirectories(Paths.get("results/figures"));

    // Очищаем старый CSV метрик для нового полного прогона.
    Files.deleteIfExists(Paths.get("results/metrics.csv"));

    ModelUtil.initStandalone(true);

    Map<String, String> baseline = readBaselineJson("params/baseline.json");
    List<Map<String, String>> cases = readSweepCsv("data/sweeps.csv");
    if (cases.isEmpty()) {
      cases.add(baseline);
    }

    for (Map<String, String> p : cases) {
      runOneCase(p, baseline);
    }

    ModelUtil.disconnect();
  }
}
