// Local binary adjacency adapter over Common Crawl's official graph explorer.
// Run with the cc-webgraph jar on the class path; stdout is exclusively binary.
import java.io.BufferedInputStream;
import java.io.BufferedOutputStream;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.EOFException;
import org.commoncrawl.webgraph.explore.Graph;
import it.unimi.dsi.webgraph.ImmutableGraph;
import it.unimi.dsi.webgraph.LazyIntIterator;

class WebGraphBridge {
    public static void main(String[] args) throws Exception {
        Graph source = new Graph(args[0]);
        DataInputStream input = new DataInputStream(new BufferedInputStream(System.in));
        DataOutputStream output = new DataOutputStream(new BufferedOutputStream(System.out));
        output.writeInt(source.graph.numNodes());
        output.flush();
        while (true) {
            int direction;
            try { direction = input.readUnsignedByte(); }
            catch (EOFException done) { break; }
            int id = input.readInt();
            if (direction > 1 || id < 0 || id >= source.graph.numNodes()) {
                throw new IllegalArgumentException("Invalid adjacency request");
            }
            ImmutableGraph graph = direction == 0 ? source.graph : source.graphT;
            output.writeInt(graph.outdegree(id));
            LazyIntIterator neighbors = graph.successors(id);
            for (int next; (next = neighbors.nextInt()) != -1;) output.writeInt(next);
            output.flush();
        }
    }
}
