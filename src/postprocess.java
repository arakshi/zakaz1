import com.comsol.model.*;
import java.io.*;
import java.util.*;

public class postprocess {

  public static class Metrics {
    public double tEval;
    public double tMax;
    public double tMin;
    public double tMean;
    public double tStd;
    public double uniformity;
  }

  public static Metrics evaluate(Model model) {
    Metrics m = new Metrics();
    m.tEval = Double.parseDouble(model.param().evaluate("Npulses/f"));

    model.result().numerical("maxV").set("time", "Npulses/f");
    model.result().numerical("minV").set("time", "Npulses/f");
    model.result().numerical("avV").set("time", "Npulses/f");

    m.tMax = model.result().numerical("maxV").getReal();
    m.tMin = model.result().numerical("minV").getReal();
    m.tMean = model.result().numerical("avV").getReal();

    // Std оценка через объемную среднюю квадрата отклонения.
    model.result().numerical().create("avVar", "AvVolume");
    model.result().numerical("avVar").selection().named("vesselDom");
    model.result().numerical("avVar").set("expr", "(T-" + m.tMean + ")^2");
    model.result().numerical("avVar").set("time", "Npulses/f");
    double var = model.result().numerical("avVar").getReal();
    if (var < 0) var = 0;

    m.tStd = Math.sqrt(var);
    m.uniformity = (m.tMax - m.tMin) / m.tMean;
    return m;
  }

  public static void exportFigures(Model model, String caseId, String geometry) {
    try {
      model.result().export().create("imgTemp", "Image");
      model.result().export("imgTemp").set("plotgroup", "pg1");
      model.result().export("imgTemp").set("pngfilename", "results/figures/" + caseId + "_temp.png");
      model.result().export("imgTemp").run();

      // T(t) в центре и на стенке сосуда.
      model.result().dataset().create("ptc", "CutPoint");
      if ("3d".equalsIgnoreCase(geometry)) {
        model.result().dataset("ptc").set("pointx", "0");
        model.result().dataset("ptc").set("pointy", "0");
        model.result().dataset("ptc").set("pointz", "depth");
      } else {
        model.result().dataset("ptc").set("pointx", "0");
        model.result().dataset("ptc").set("pointy", "depth");
      }

      model.result().dataset().create("ptw", "CutPoint");
      if ("3d".equalsIgnoreCase(geometry)) {
        model.result().dataset("ptw").set("pointx", "D/2");
        model.result().dataset("ptw").set("pointy", "0");
        model.result().dataset("ptw").set("pointz", "depth");
      } else {
        model.result().dataset("ptw").set("pointx", "D/2");
        model.result().dataset("ptw").set("pointy", "depth");
      }

      model.result().create("pgT", "PlotGroup1D");
      model.result("pgT").create("g1", "Global");
      model.result("pgT").feature("g1").set("expr", new String[]{"T", "T"});
      model.result("pgT").feature("g1").set("data", "dset1");

      model.result().export().create("imgTime", "Image");
      model.result().export("imgTime").set("plotgroup", "pgT");
      model.result().export("imgTime").set("pngfilename", "results/figures/" + caseId + "_time.png");
      model.result().export("imgTime").run();
    } catch (Exception ignored) {
      // Экспорт графики не должен ломать sweep.
    }
  }

  public static void appendMetricsCsv(String outPath, Map<String, String> p, Metrics m) throws IOException {
    boolean writeHeader = !(new File(outPath).exists());
    try (FileWriter fw = new FileWriter(outPath, true)) {
      if (writeHeader) {
        fw.write("case_id,geometry,mode,D,depth,tp,f,Npulses,w0,t_eval,Tmax_vessel,Tmin_vessel,Tmean_vessel,Std_vessel,UniformityIndex\n");
      }
      fw.write(String.join(",",
          p.get("case_id"),
          p.get("geometry"),
          p.get("mode"),
          p.get("D"),
          p.get("depth"),
          p.get("tp"),
          p.get("f"),
          p.get("Npulses"),
          p.get("w0"),
          Double.toString(m.tEval),
          Double.toString(m.tMax),
          Double.toString(m.tMin),
          Double.toString(m.tMean),
          Double.toString(m.tStd),
          Double.toString(m.uniformity)
      ));
      fw.write("\n");
    }
  }
}
