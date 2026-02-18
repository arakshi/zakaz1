import com.comsol.model.*;
import com.comsol.model.util.*;
import java.util.Map;

public class build_model_2d_axi {

  public static Model buildFromMap(Map<String, String> p, String caseId) {
    Model model = ModelUtil.create("Model");
    model.modelPath(".");
    model.label(caseId + "_2daxi.mph");

    setParams(model, p);
    createGeometry(model);
    createMaterial(model);
    createPhysics(model, p);
    createMesh(model);
    createStudy(model);
    createResults(model);
    return model;
  }

  private static void setParams(Model model, Map<String, String> p) {
    for (Map.Entry<String, String> e : p.entrySet()) {
      model.param().set(e.getKey(), e.getValue());
    }

    model.param().set("pi", "3.141592653589793");
    model.param().set("t_end", "Npulses/f + extra_cool");
    model.param().set("dtmax", "tp*dtmax_factor");

    model.param().set("pulse", "if(mod(t,1/f)<tp,1,0)");
    model.param().set("Q578", "A_578*exp(-2*r^2/w0^2)*exp(-mu_eff_578*z)*pulse");
    model.param().set("Q511", "A_511*exp(-2*r^2/w0^2)*exp(-mu_eff_511*z)*pulse");
    model.param().set("Qlaser", "if(modeflag<1.5,Q578,p578*Q578+p511*Q511)");
    model.param().set("Qperf", "-wb*cb*(T-T_blood)");
  }

  private static void createGeometry(Model model) {
    model.component().create("comp1", true);
    model.component("comp1").geom().create("geom1", 2);
    model.component("comp1").geom("geom1").axisymmetric(true);
    model.component("comp1").geom("geom1").lengthUnit("m");

    model.component("comp1").geom("geom1").create("r1", "Rectangle");
    model.component("comp1").geom("geom1").feature("r1").set("size", new String[]{"Rmax2D", "Zmax2D"});
    model.component("comp1").geom("geom1").feature("r1").set("pos", new String[]{"0", "0"});

    model.component("comp1").geom("geom1").create("c1", "Circle");
    model.component("comp1").geom("geom1").feature("c1").set("r", "D/2");
    model.component("comp1").geom("geom1").feature("c1").set("pos", new String[]{"0", "depth"});

    model.component("comp1").geom("geom1").run();

    model.component("comp1").selection().create("vesselDom", "Explicit");
    model.component("comp1").selection("vesselDom").geom("geom1", 2);
    model.component("comp1").selection("vesselDom").set(new int[]{2});
  }

  private static void createMaterial(Model model) {
    model.component("comp1").material().create("mat1", "Common");
    model.component("comp1").material("mat1").propertyGroup("def").set("thermalconductivity", new String[]{"k", "0", "0", "k"});
    model.component("comp1").material("mat1").propertyGroup("def").set("density", "rho");
    model.component("comp1").material("mat1").propertyGroup("def").set("heatcapacity", "Cp");
    model.component("comp1").material("mat1").selection().all();
  }

  private static void createPhysics(Model model, Map<String, String> p) {
    boolean useBioheat = "1".equals(p.get("useBioheat"));

    if (useBioheat) {
      // Если тег BioHeat отличается, используйте ветку ht ниже.
      model.component("comp1").physics().create("bh", "BioHeat", "geom1");
      model.component("comp1").physics("bh").feature("hf1").set("Tinit", "T0");
      model.component("comp1").physics("bh").create("hs1", "HeatSource", 2);
      model.component("comp1").physics("bh").feature("hs1").set("Q0", "Qlaser");
    } else {
      model.component("comp1").physics().create("ht", "HeatTransferInSolids", "geom1");
      model.component("comp1").physics("ht").feature("init1").set("Tinit", "T0");
      model.component("comp1").physics("ht").create("hs1", "HeatSource", 2);
      model.component("comp1").physics("ht").feature("hs1").set("Q0", "Qlaser+Qperf");
    }
  }

  private static void createMesh(Model model) {
    model.component("comp1").mesh().create("mesh1");
    model.component("comp1").mesh("mesh1").create("ftri1", "FreeTri");
    model.component("comp1").mesh("mesh1").create("size1", "Size");
    model.component("comp1").mesh("mesh1").feature("size1").set("hauto", 3);

    model.component("comp1").mesh("mesh1").create("size2", "Size");
    model.component("comp1").mesh("mesh1").feature("size2").selection().named("vesselDom");
    model.component("comp1").mesh("mesh1").feature("size2").set("hauto", 2);

    model.component("comp1").mesh("mesh1").run();
  }

  private static void createStudy(Model model) {
    model.study().create("std1");
    model.study("std1").create("time", "Transient");
    model.study("std1").feature("time").set("tlist", "range(0,dtmax,t_end)");

    model.sol().create("sol1");
    model.sol("sol1").study("std1");
    model.sol("sol1").create("st1", "StudyStep");
    model.sol("sol1").create("v1", "Variables");
    model.sol("sol1").create("t1", "Time");
    model.sol("sol1").feature("t1").set("tlist", "range(0,dtmax,t_end)");
    model.sol("sol1").feature("t1").set("maxstepbdf", "dtmax");
    model.sol("sol1").feature("t1").set("rtol", "1e-3");
    model.sol("sol1").attach("std1");
  }

  private static void createResults(Model model) {
    model.result().create("pg1", "PlotGroup2D");
    model.result("pg1").create("surf1", "Surface");
    model.result("pg1").feature("surf1").set("expr", "T");

    model.result().numerical().create("maxV", "MaxVolume");
    model.result().numerical("maxV").selection().named("vesselDom");
    model.result().numerical("maxV").set("expr", "T");

    model.result().numerical().create("minV", "MinVolume");
    model.result().numerical("minV").selection().named("vesselDom");
    model.result().numerical("minV").set("expr", "T");

    model.result().numerical().create("avV", "AvVolume");
    model.result().numerical("avV").selection().named("vesselDom");
    model.result().numerical("avV").set("expr", "T");
  }


  private static java.util.Map<String, String> defaultParamsForStandalone() {
    java.util.Map<String, String> p = new java.util.LinkedHashMap<String, String>();
    p.put("case_id", "manual");
    p.put("geometry", "2d");
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

  public static void main(String[] args) throws Exception {
    ModelUtil.initStandalone(true);
    Model model = buildFromMap(defaultParamsForStandalone(), "manual_2d");
    model.param().set("modeflag", "1");
    model.sol("sol1").runAll();
    model.save("results/models/manual_2d.mph");
    ModelUtil.disconnect();
  }
}
